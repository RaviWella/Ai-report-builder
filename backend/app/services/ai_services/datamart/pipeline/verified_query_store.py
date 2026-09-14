"""
Verified question → SQL examples (Tier-B RAG without a vector DB).

Loads curated pairs from ``verified_queries.yaml`` and ranks them by token overlap
with the user question. Used before the LLM when no governed template matches.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

from ..config import SEARCH_STOP_WORDS, DATAMART_VERIFIED_MIN_SCORE
from ..workspace.runtime_context import mart_schema_for_hints

logger = logging.getLogger("ai_services.datamart.verified_queries")

_STORE_PATH = Path(__file__).resolve().parent.parent / "verified_queries.yaml"
# Do not filter verified entries when classification is ambiguous.
_DOMAIN_FILTER_SKIP = frozenset({"", "mixed", "unknown"})


@dataclass(frozen=True, slots=True)
class VerifiedQuery:
    id: str
    question: str
    sql_template: str
    tables: tuple[str, ...]
    domain: str = ""
    narrative: str = ""


def _tokens(text: str) -> set[str]:
    return {
        t
        for t in re.findall(r"[a-z0-9_]+", text.lower())
        if t not in SEARCH_STOP_WORDS and len(t) > 2
    }


def _score(question: str, entry: VerifiedQuery) -> int:
    q_tokens = _tokens(question)
    if not q_tokens:
        return 0
    e_tokens = _tokens(entry.question)
    if not e_tokens:
        return 0
    overlap = len(q_tokens & e_tokens)
    # Boost when domain keywords appear in both
    domain_tokens = _tokens(entry.domain.replace("_", " "))
    overlap += len(q_tokens & domain_tokens)
    # Exact/near-exact bank question match
    if question.strip().lower() == entry.question.strip().lower():
        overlap += 20
    return overlap


@lru_cache(maxsize=4)
def _load_entries(path_str: str) -> tuple[VerifiedQuery, ...]:
    path = Path(path_str)
    if not path.is_file():
        logger.warning("Verified queries file missing: %s", path)
        return ()
    try:
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load verified queries: %s", exc)
        return ()

    entries: list[VerifiedQuery] = []
    for block in data.get("queries") or []:
        if not isinstance(block, dict):
            continue
        q = str(block.get("question") or "").strip()
        sql = str(block.get("sql") or block.get("sql_template") or "").strip()
        if not q or not sql:
            continue
        tables_raw = block.get("tables") or block.get("expect_tables") or []
        tables = tuple(str(t).strip() for t in tables_raw if str(t).strip())
        entries.append(
            VerifiedQuery(
                id=str(block.get("id") or f"vq_{len(entries)}"),
                question=q,
                sql_template=sql,
                tables=tables,
                domain=str(block.get("domain") or block.get("eval_domain") or ""),
                narrative=str(block.get("narrative") or ""),
            )
        )
    return tuple(entries)


def load_all_verified_queries() -> tuple[VerifiedQuery, ...]:
    """All curated Tier-B examples (for registry / eval)."""
    return _load_entries(str(_STORE_PATH))


def clear_verified_query_cache() -> None:
    _load_entries.cache_clear()


def materialize_sql(sql_template: str, *, limit: int) -> str:
    schema = mart_schema_for_hints()
    return (
        sql_template.replace("{schema}", schema)
        .replace("{limit}", str(limit))
        .strip()
    )


def peek_verified_query_tables(
    question: str,
    *,
    domain: str | None = None,
    min_score: int = 4,
) -> tuple[str, ...]:
    """
    Tables from the best matching verified entry — used to seed schema link
    before Tier-B resolution (does not require tables to already be grounded).
    """
    entries = _load_entries(str(_STORE_PATH))
    if not entries:
        return ()

    domain_l = (domain or "").strip().lower()
    scored: list[tuple[int, VerifiedQuery]] = []
    for entry in entries:
        if (
            domain_l
            and domain_l not in _DOMAIN_FILTER_SKIP
            and entry.domain
            and entry.domain.lower() != domain_l
        ):
            continue
        score = _score(question, entry)
        if score >= min_score:
            scored.append((score, entry))
    if not scored:
        return ()
    scored.sort(key=lambda x: (-x[0], x[1].id))
    return scored[0][1].tables


def retrieve_verified_sql(
    question: str,
    *,
    grounded_tables: set[str],
    domain: str | None = None,
    min_score: int | None = None,
    top_k: int = 1,
) -> Optional[tuple[str, str, str]]:
    """
  Return ``(sql, source_tag, narrative)`` for the best matching verified example.

  Requires at least one expected table to appear in the grounded allowlist when
  the entry declares tables.
    """
    entries = _load_entries(str(_STORE_PATH))
    if not entries:
        return None

    score_floor = min_score if min_score is not None else DATAMART_VERIFIED_MIN_SCORE

    grounded_lower = {t.lower() for t in grounded_tables}
    scored: list[tuple[int, VerifiedQuery]] = []
    domain_l = (domain or "").strip().lower()
    for entry in entries:
        if (
            domain_l
            and domain_l not in _DOMAIN_FILTER_SKIP
            and entry.domain
            and entry.domain.lower() != domain_l
        ):
            continue
        score = _score(question, entry)
        if score < score_floor:
            continue
        if entry.tables:
            if not any(t.lower() in grounded_lower for t in entry.tables):
                if score < 8:
                    continue
        scored.append((score, entry))

    if not scored:
        return None

    scored.sort(key=lambda x: (-x[0], x[1].id))
    best = scored[0][1]
    from ..config import MAX_RESULT_ROWS

    sql = materialize_sql(best.sql_template, limit=MAX_RESULT_ROWS)
    narrative = best.narrative or f"Verified query pattern ({best.id})."
    return sql, f"verified:{best.id}", narrative
