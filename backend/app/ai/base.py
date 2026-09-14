"""AIProvider interface (Architecture §4.4, D9).

The AI assistant has exactly THREE tasks, all metadata-only (SRS §8.1):
  1. excel_mapping        — column headers + inferred types -> ref mapping suggestion
  2. natural_language     — NL request + semantic field names -> data_spec
  3. adjustment_chat      — current spec + instruction -> updated data_spec

The provider returns a STRUCTURED spec/mapping ONLY. It never returns SQL and
never receives row-level data. Swapping providers (external <-> self-hosted) is a
config change, never a code change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class FieldMetadata:
    """Metadata-only description of one semantic field handed to the AI."""

    ref: str
    label: str
    type: str
    role: str
    entity: str
    description: str | None = None
    allowed_aggregations: list[str] = field(default_factory=list)


@dataclass
class ExcelColumnMeta:
    """A single uploaded-Excel column AFTER local stripping. NO data rows here."""

    header: str
    inferred_type: str
    sample_is_empty: bool = True  # rows were stripped; kept only as a sanity flag


@dataclass
class AISpecResult:
    """What every AI task returns: a data_spec (or partial) plus an explanation."""

    data_spec: dict
    rationale: str
    confidence: float = 0.0


@dataclass
class AIMappingResult:
    """Excel-mapping suggestion: header -> proposed semantic ref (human confirms)."""

    mappings: list[dict]  # [{"header","suggested_ref","confidence"}]
    rationale: str


class AIProvider(ABC):
    """Provider-agnostic adapter. Implementations assemble metadata-only payloads."""

    @abstractmethod
    def excel_mapping(
        self, columns: list[ExcelColumnMeta], fields: list[FieldMetadata]
    ) -> AIMappingResult: ...

    @abstractmethod
    def natural_language(
        self, request: str, fields: list[FieldMetadata]
    ) -> AISpecResult: ...

    @abstractmethod
    def adjustment_chat(
        self, instruction: str, current_spec: dict, fields: list[FieldMetadata]
    ) -> AISpecResult: ...

    @abstractmethod
    def derive_field(self, description: str, fields: list[FieldMetadata]) -> dict:
        """Turn a plain-language description (or rough formula) into a STRUCTURED
        derived-field spec (a CalculatedField dict — formula or banding). Returns a
        dict; never raw SQL. The caller validates it against the Pydantic model."""
        ...

    def converse(self, question: str, context: str) -> str:
        """Answer a plain-language question ABOUT a result already on screen — no SQL,
        no report spec, just read the provided table and reply concisely. Concrete
        providers supply `_complete(system, user)`."""
        system = (
            "You are an HR analytics assistant. Answer the user's question using ONLY "
            "the result table provided. Be concise — 1 to 3 sentences. Never invent "
            "numbers, never write SQL. If the table can't answer it, say so plainly."
        )
        user = f"RESULT ON SCREEN:\n{context}\n\nQUESTION: {question}"
        return self._complete(system, user)  # type: ignore[attr-defined]

    def extract_letter(self, text: str, fields: list["FieldMetadata"]) -> str:
        """Turn a sample letter into a template: find the PER-RECIPIENT DYNAMIC values
        (names, addresses, dates, amounts, designations, ids — anything that differs
        per employee) and map each to a data field ref. Static boilerplate is left
        alone. Returns STRICT JSON (the caller parses + validates refs). Metadata only —
        the field list carries no data, and the letter text is a template sample."""
        system, user = build_extract_letter_prompt(text, fields)
        return self._complete(system, user)  # type: ignore[attr-defined]


def build_extract_letter_prompt(text: str, fields: list[FieldMetadata]) -> tuple[str, str]:
    """The (system, user) prompt pair for extract_letter — pulled out of the
    provider method so document_ai_runner.py's SDK-based path reuses the exact
    same prompt text rather than restating it."""
    catalog = "\n".join(f"{f.ref} — {f.label}" for f in fields)
    system = (
        "You convert a sample HR letter into a REUSABLE TEMPLATE. Find every "
        "PER-RECIPIENT DYNAMIC value — things that change for each employee: their "
        "name, address, dates, salary/amount figures, designation, numbers — and map "
        "each to a data field. Leave static boilerplate sentences untouched. You NEVER "
        "invent field refs: use ONLY a ref from the provided list, or null if none "
        "fits. Copy each value EXACTLY as it appears so it can be located. Output STRICT "
        "JSON only, no prose, no code fences."
    )
    user = (
        "AVAILABLE FIELDS (ref — label):\n" + (catalog or "(none)") +
        "\n\nLETTER SAMPLE:\n" + text +
        "\n\nReturn JSON exactly: {\"replacements\": [{\"text\": \"<verbatim substring "
        "from the letter>\", \"ref\": \"<a ref from the list, or null>\"}]}. Include "
        "EVERY dynamic value (each occurrence's exact text). Do NOT include static "
        "sentences. If unsure of a field, still list the value with ref null."
    )
    return system, user
