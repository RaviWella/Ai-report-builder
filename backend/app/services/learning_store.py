"""Canonical-intent / learning store — "understand once, reuse forever".

The semantic layer turns a question into a DataSpec. This store sits in front of
that step: it remembers, per tenant, which NORMALISED phrasing resolved to which
spec, and replays it. So once any user asks a question, every later user who asks
the same thing — in any phrasing that normalises equal — gets the *same* spec, and
therefore the *same* answer. That is the consistency guarantee the architecture is
built on: re-derivation (and the drift it can cause) is avoided, and coverage
compounds as more questions are asked.

Two keys:
  - `phrase_key`  — a normalised form of the question (lower-cased, de-noised,
                    token-sorted) so trivial wording differences collapse to one
                    lookup key.
  - `signature`   — a hash of the *canonical spec* (entity + sorted refs/filters/
                    grouping/aggregations). Many phrasings that mean the same thing
                    share a signature; it lets us spot when two phrasings diverge.

The store keeps only the spec (semantic refs, never physical SQL), so a learned
entry stays valid across catalogue versions as long as the refs still exist — the
caller re-validates on replay and the entry is dropped if the catalogue moved on.
"""

from __future__ import annotations

import hashlib
import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.metadata import LearnedIntent

log = get_logger(__name__)

# Words that don't change *which* data a question asks for — dropped before keying
# so "show me headcount by department" and "department-wise headcount" collapse.
# Deliberately conservative: status words, numbers and concept nouns are KEPT, so
# "active employee count" and "employee count" stay distinct intents.
_STOPWORDS = {
    "a", "an", "the", "of", "for", "to", "in", "on", "by", "per", "and", "with",
    "me", "my", "our", "us", "please", "give", "show", "showing", "list", "listing",
    "get", "see", "want", "need", "display", "provide", "generate", "report",
    "reports", "data", "all", "them", "their", "is", "are", "do", "we", "have",
    "has", "grouped", "group", "wise", "breakdown", "across", "between",
    "can", "could", "would", "i", "pls", "kindly",
}
_TOKEN = re.compile(r"[a-z0-9]+")


class LearningStore:
    """Per-tenant canonical-intent store over the `learned_intent` table."""

    def __init__(self, db: Session):
        self.db = db

    # ---- keys -------------------------------------------------------------- #
    @staticmethod
    def phrase_key(text: str) -> str:
        """Normalise a question to a stable lookup key: lower-case, keep only
        meaningful tokens, sort them. Word order and noise no longer matter, but
        content words (department, active, net, 2) still distinguish intents."""
        toks = [t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS]
        return " ".join(sorted(toks))

    @staticmethod
    def signature(spec: dict) -> str:
        """A hash of the canonical spec — its semantic content, order-independent.
        Two phrasings that resolve to the same data share a signature."""
        canon = {
            "entity": spec.get("entity"),
            "fields": sorted(f.get("ref") for f in spec.get("fields", []) if f.get("ref")),
            "filters": sorted(
                f"{f.get('ref')}|{f.get('op')}|{f.get('value')}" for f in spec.get("filters", [])
            ),
            "group_by": sorted(spec.get("group_by", [])),
            "aggregations": sorted(
                f"{a.get('ref')}|{a.get('fn')}" for a in spec.get("aggregations", [])
            ),
        }
        blob = json.dumps(canon, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()[:16]

    # ---- operations -------------------------------------------------------- #
    def lookup(self, tenant_id: str, text: str) -> dict | None:
        """Return `{"spec": ..., "certified": bool}` for this phrasing, or None. Bumps
        usage counters on a hit. The caller MUST re-validate the spec against the live
        catalogue before serving (and call `forget` if it no longer validates)."""
        key = self.phrase_key(text)
        if not key:
            return None
        row = self.db.scalar(
            select(LearnedIntent).where(
                LearnedIntent.phrase_key == key
            )
        )
        if row is None:
            return None
        row.hits += 1
        from sqlalchemy import func as _f

        row.last_used_at = _f.now()
        self.db.commit()
        return {"spec": dict(row.spec), "certified": row.certified}

    def remember(
        self, tenant_id: str, text: str, spec: dict, *, source: str, user_id: str
    ) -> None:
        """Learn a (phrasing → spec) mapping. Idempotent per (tenant, phrase_key):
        a certified entry is never overwritten; otherwise the latest resolution
        wins. Best-effort — never raises into the chat path."""
        key = self.phrase_key(text)
        if not key:
            return
        try:
            sig = self.signature(spec)
            row = self.db.scalar(
                select(LearnedIntent).where(
                    LearnedIntent.phrase_key == key
                )
            )
            if row is None:
                self.db.add(
                    LearnedIntent(
                        phrase_key=key, phrase_sample=text[:500],
                        spec=spec, signature=sig, source=source, created_by=user_id,
                    )
                )
            elif not row.certified:
                row.spec, row.signature, row.source = spec, sig, source
            self.db.commit()
        except Exception as exc:  # noqa: BLE001 - learning must never break the chat
            self.db.rollback()
            log.warning("learn_remember_failed", error=str(exc)[:160])

    def forget(self, tenant_id: str, text: str) -> None:
        """Drop a learned entry (e.g. it no longer validates after a catalogue
        change). Best-effort."""
        key = self.phrase_key(text)
        try:
            row = self.db.scalar(
                select(LearnedIntent).where(
                    LearnedIntent.phrase_key == key
                )
            )
            if row is not None:
                self.db.delete(row)
                self.db.commit()
        except Exception:  # noqa: BLE001
            self.db.rollback()

    # ---- governance (#5: certified canonical mappings) --------------------- #
    @staticmethod
    def _to_dict(r: LearnedIntent) -> dict:
        return {
            "id": r.id, "phrase_key": r.phrase_key, "phrase_sample": r.phrase_sample,
            "spec": r.spec, "signature": r.signature, "source": r.source,
            "certified": r.certified, "hits": r.hits,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "last_used_at": r.last_used_at.isoformat() if r.last_used_at else None,
        }

    def list(self, tenant_id: str, limit: int = 200) -> list[dict]:
        """All learned intents for a tenant — certified first, then most-used. The
        governance view an admin uses to certify/correct the canonical mappings."""
        rows = self.db.scalars(
            select(LearnedIntent)
            .where(True)
            .order_by(
                LearnedIntent.certified.desc(),
                LearnedIntent.hits.desc(),
                LearnedIntent.last_used_at.desc(),
            )
            .limit(limit)
        ).all()
        return [self._to_dict(r) for r in rows]

    def set_certified(self, tenant_id: str, intent_id: str, certified: bool) -> dict | None:
        """Certify (lock as authoritative) or un-certify a learned intent. A certified
        intent is never overwritten by re-resolution — it is the governed canonical
        mapping for that question. Returns the updated row, or None if not found."""
        row = self.db.scalar(
            select(LearnedIntent).where(
                LearnedIntent.id == intent_id
            )
        )
        if row is None:
            return None
        row.certified = certified
        if certified:
            row.source = "certified"
        self.db.commit()
        return self._to_dict(row)

    def delete_by_id(self, tenant_id: str, intent_id: str) -> bool:
        """Remove a learned intent (e.g. a wrong mapping an admin wants re-derived)."""
        row = self.db.scalar(
            select(LearnedIntent).where(
                LearnedIntent.id == intent_id
            )
        )
        if row is None:
            return False
        self.db.delete(row)
        self.db.commit()
        return True
