"""
Unified knowledge loader (S5): question bank, verified SQL, catalog templates.

Single entry point for eval harnesses and tooling — not used on the hot path yet.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

import yaml

from ..domain_sql.report_spec import compile_report_spec
from ..orchestration.intent_router import ChatIntent
from .verified_query_store import (
    VerifiedQuery,
    clear_verified_query_cache,
    load_all_verified_queries,
)

_BANK_DEFAULT = (
    Path(__file__).resolve().parents[5] / "tools" / "datamart_question_bank.yaml"
)
_VERIFIED_DEFAULT = Path(__file__).resolve().parents[1] / "verified_queries.yaml"


@dataclass(frozen=True, slots=True)
class BankEntry:
    section: str
    question: str
    expect_tables: tuple[str, ...]
    eval_domain: str
    template: str | None
    require_all_tables: bool


@dataclass
class KnowledgeRegistry:
    """Loaded question bank + verified examples + discovered template ids."""

    bank_path: Path
    verified_path: Path
    bank: tuple[BankEntry, ...] = field(default_factory=tuple)
    verified: tuple[VerifiedQuery, ...] = field(default_factory=tuple)
    template_ids: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def load(
        cls,
        *,
        bank_path: Path | None = None,
        verified_path: Path | None = None,
    ) -> KnowledgeRegistry:
        bank_p = bank_path or _BANK_DEFAULT
        ver_p = verified_path or _VERIFIED_DEFAULT
        bank = tuple(_load_bank_entries(bank_p))
        clear_verified_query_cache()
        verified = load_all_verified_queries()
        templates: set[str] = set()
        for entry in bank:
            if entry.template:
                templates.add(entry.template)
            spec = compile_report_spec(entry.question, chat_intent=ChatIntent.NEW_QUERY)
            if spec.template_id:
                templates.add(spec.template_id)
        return cls(
            bank_path=bank_p,
            verified_path=ver_p,
            bank=bank,
            verified=verified,
            template_ids=frozenset(templates),
        )

    def iter_bank(self) -> Iterator[BankEntry]:
        yield from self.bank

    def verified_for_domain(self, domain: str) -> tuple[VerifiedQuery, ...]:
        d = domain.strip().lower()
        return tuple(v for v in self.verified if v.domain.lower() == d)

    def bank_meta(self) -> dict[str, Any]:
        raw = yaml.safe_load(self.bank_path.read_text(encoding="utf-8")) or {}
        return dict(raw.get("meta") or {})


def _load_bank_entries(path: Path) -> list[BankEntry]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: list[BankEntry] = []
    for section, entries in raw.items():
        if section == "meta" or not isinstance(entries, list):
            continue
        for block in entries:
            if not isinstance(block, dict) or not block.get("question"):
                continue
            expect = block.get("expect_tables") or []
            out.append(
                BankEntry(
                    section=str(section),
                    question=str(block["question"]).strip(),
                    expect_tables=tuple(str(t).strip() for t in expect if str(t).strip()),
                    eval_domain=str(block.get("eval_domain") or "").strip().lower(),
                    template=(
                        str(block["template"]).strip()
                        if block.get("template")
                        else None
                    ),
                    require_all_tables=bool(block.get("require_all_tables")),
                )
            )
    return out


@lru_cache(maxsize=2)
def get_knowledge_registry(
    bank_path_str: str,
    verified_path_str: str,
) -> KnowledgeRegistry:
    return KnowledgeRegistry.load(
        bank_path=Path(bank_path_str),
        verified_path=Path(verified_path_str),
    )
