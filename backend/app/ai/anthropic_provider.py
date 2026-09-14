"""Default AI provider — Anthropic API under ZDR + BAA (SRS §8.3, Architecture §3.3).

Payloads are METADATA ONLY. The model is asked to return strict JSON which we
parse into a dict; the caller (ai_service) validates it against the Pydantic
DataSpec before it is ever trusted. No PII, no SQL crosses this boundary.
"""

from __future__ import annotations

import json
import re

from anthropic import Anthropic

from app.ai.base import (
    AIMappingResult,
    AIProvider,
    AISpecResult,
    ExcelColumnMeta,
    FieldMetadata,
)
from app.ai.prompts.system_prompts import (
    ADJUST_SYSTEM,
    DERIVE_FIELD_SYSTEM,
    EXCEL_MAPPING_SYSTEM,
    NL_SYSTEM,
)
from app.core.config import settings


def _fields_payload(fields: list[FieldMetadata]) -> str:
    """Compact, one-line-per-field listing of the metadata-only catalogue.

    Terse on purpose: small self-hosted models (e.g. mimo-v2.5, 4k context) can't
    take a verbose JSON dump of 140 fields. Format: `ref | label | type | role`.
    Still metadata only — no physical names, no data.
    """
    lines = [
        f"{f.ref} | {f.label} | {f.type} | {'mea' if f.role == 'measure' else 'dim'}"
        for f in fields
    ]
    return "\n".join(lines)


_MAPPING_OBJ = re.compile(
    r'\{\s*"header"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"suggested_ref"\s*:\s*'
    r'(null|"(?:[^"\\]|\\.)*")\s*,\s*"confidence"\s*:\s*([0-9.]+)',
)


def _extract_json(text: str) -> dict:
    if not text or not isinstance(text, str):
        raise ValueError("AI returned an empty response")
    text = text.strip()
    if "```" in text:
        # take the fenced block most likely to hold JSON
        for part in text.split("```"):
            p = part[4:] if part.lstrip().lower().startswith("json") else part
            if "{" in p:
                text = p
                break
    start = text.find("{")
    if start == -1:
        raise ValueError("AI response contained no JSON object")
    snippet = text[start:]
    # 1) straight parse
    try:
        return json.loads(snippet)
    except json.JSONDecodeError:
        pass
    # 2) trim to the last closing brace (handles trailing prose)
    end = snippet.rfind("}")
    if end != -1:
        try:
            return json.loads(snippet[: end + 1])
        except json.JSONDecodeError:
            pass
    # 3) truncated mapping array -> recover the complete mapping objects we got
    mappings = [
        {"header": m.group(1), "suggested_ref": None if m.group(2) == "null" else m.group(2).strip('"'),
         "confidence": float(m.group(3))}
        for m in _MAPPING_OBJ.finditer(snippet)
    ]
    if mappings:
        return {"mappings": mappings, "rationale": "Recovered from a long mapping response."}
    raise ValueError("AI response was not valid JSON")


class AnthropicProvider(AIProvider):
    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        # UI-entered key (passed in) takes precedence over the env fallback.
        self._client = Anthropic(api_key=api_key or settings.anthropic_api_key)
        self._model = model or settings.ai_model
        self._max_tokens = settings.ai_max_tokens

    def _complete(self, system: str, user: str) -> str:
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in msg.content if block.type == "text")

    def natural_language(self, request: str, fields: list[FieldMetadata]) -> AISpecResult:
        user = f"AVAILABLE FIELDS:\n{_fields_payload(fields)}\n\nREPORT REQUEST:\n{request}"
        spec = _extract_json(self._complete(NL_SYSTEM, user))
        return AISpecResult(data_spec=spec, rationale="Generated from natural-language request.")

    def adjustment_chat(
        self, instruction: str, current_spec: dict, fields: list[FieldMetadata]
    ) -> AISpecResult:
        user = (
            f"AVAILABLE FIELDS:\n{_fields_payload(fields)}\n\n"
            f"CURRENT SPEC:\n{json.dumps(current_spec, ensure_ascii=False)}\n\n"
            f"INSTRUCTION:\n{instruction}"
        )
        spec = _extract_json(self._complete(ADJUST_SYSTEM, user))
        return AISpecResult(data_spec=spec, rationale="Updated from adjustment instruction.")

    def derive_field(self, description: str, fields: list[FieldMetadata]) -> dict:
        user = f"AVAILABLE FIELDS:\n{_fields_payload(fields)}\n\nDESCRIBE THE COLUMN:\n{description}"
        return _extract_json(self._complete(DERIVE_FIELD_SYSTEM, user))

    def excel_mapping(
        self, columns: list[ExcelColumnMeta], fields: list[FieldMetadata]
    ) -> AIMappingResult:
        cols = json.dumps(
            [{"header": c.header, "inferred_type": c.inferred_type} for c in columns],
            ensure_ascii=False,
        )
        user = f"AVAILABLE FIELDS:\n{_fields_payload(fields)}\n\nUPLOADED HEADERS (rows stripped):\n{cols}"
        result = _extract_json(self._complete(EXCEL_MAPPING_SYSTEM, user))
        return AIMappingResult(
            mappings=result.get("mappings", []), rationale=result.get("rationale", "")
        )
