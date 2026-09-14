"""Data-type classifier for the MintHRM Data Intake layer.

Scores a ``FileProfile`` against every ``CanonicalTarget`` in the registry.
The score is the fraction of canonical fields whose aliases matched a source
header, weighted by required-field hits.

Deterministic and explainable: the result includes per-target scores and the
matched aliases.  AI may suggest re-ranking later, but classification output
is reproducible from the headers alone.

Ported from mint-analytics data_intake/classifier.py — domain changed to HR,
logic unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from app.services.data_intake.canonical_targets import (
    CANONICAL_TARGETS,
    UNKNOWN_DATA_TYPE,
    CanonicalTarget,
)

DEFAULT_CONFIDENCE_THRESHOLD = 0.4


# ── Result types ──────────────────────────────────────────────────


@dataclass
class TargetScore:
    data_type: str
    score: float
    matched_fields: List[str]
    matched_headers: List[str]
    required_hits: int
    required_total: int


@dataclass
class ClassificationResult:
    detected_data_type: str
    confidence: float
    sheet_used: str
    candidates: List[TargetScore]   # sorted desc by score
    threshold: float

    def to_dict(self) -> dict:
        return {
            "detected_data_type": self.detected_data_type,
            "confidence": round(self.confidence, 4),
            "sheet_used": self.sheet_used,
            "threshold": self.threshold,
            "candidates": [
                {
                    "data_type":      c.data_type,
                    "score":          round(c.score, 4),
                    "matched_fields": c.matched_fields,
                    "matched_headers": c.matched_headers,
                    "required_hits":  c.required_hits,
                    "required_total": c.required_total,
                }
                for c in self.candidates
            ],
        }


# ── Public API ────────────────────────────────────────────────────


def classify(
    profile: "FileProfile",  # noqa: F821 — imported lazily to avoid circular
    targets: Iterable[CanonicalTarget] = CANONICAL_TARGETS,
    threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> ClassificationResult:
    """Score ``profile`` against every target and return the best match."""
    if not profile.sheets:
        return ClassificationResult(
            detected_data_type=UNKNOWN_DATA_TYPE,
            confidence=0.0,
            sheet_used="",
            candidates=[],
            threshold=threshold,
        )

    # Pick the sheet with the most non-empty headers — strongest signal.
    best_sheet = max(profile.sheets, key=lambda s: sum(1 for h in s.headers if h))

    scored = [_score_target(t, best_sheet) for t in targets]
    scored.sort(key=lambda c: c.score, reverse=True)

    if not scored or scored[0].score < threshold:
        detected = UNKNOWN_DATA_TYPE
        conf = scored[0].score if scored else 0.0
    else:
        detected = scored[0].data_type
        conf = scored[0].score

    return ClassificationResult(
        detected_data_type=detected,
        confidence=conf,
        sheet_used=best_sheet.name,
        candidates=scored,
        threshold=threshold,
    )


# ── Internal ──────────────────────────────────────────────────────


def _norm(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum())


def _score_target(target: CanonicalTarget, sheet: "SheetProfile") -> TargetScore:  # noqa: F821
    aliases = target.field_aliases()
    headers_norm = [(h, _norm(h)) for h in sheet.headers if h]

    matched_fields: set[str] = set()
    matched_headers: List[str] = []
    for raw_h, norm_h in headers_norm:
        canonical = aliases.get(norm_h)
        if canonical and canonical not in matched_fields:
            matched_fields.add(canonical)
            matched_headers.append(raw_h)

    required = target.required_field_names()
    required_hits = sum(1 for r in required if r in matched_fields)

    n_fields = len(target.fields)
    base = len(matched_fields) / n_fields if n_fields else 0.0

    if required:
        req_ratio = required_hits / len(required)
        score = 0.6 * base + 0.4 * req_ratio
    else:
        score = base

    return TargetScore(
        data_type=target.data_type,
        score=score,
        matched_fields=sorted(matched_fields),
        matched_headers=matched_headers,
        required_hits=required_hits,
        required_total=len(required),
    )
