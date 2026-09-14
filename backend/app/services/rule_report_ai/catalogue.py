"""Ground the rule-report chat in the tenant's REAL physical schema — otherwise
an AI mapping a legacy SQL query (or just naming columns from memory) will
invent plausible-but-wrong table and column names, which only shows up as a
compile error several turns later.

Deliberately the ONLY grounding source: the curated field catalogue
(SemanticService) that Report Builder already owns as a generic abstraction
over "whatever physical schema this tenant's datamart has." Report Builder is
a common platform across datamarts/warehouses — it must not hardcode
knowledge of any ONE data warehouse's internal layering (schema names,
naming conventions, internal lookup tables). Exposing anything beyond the
curated mart-level catalogue (record-level fact/dimension detail, legacy
code dictionaries, ...) is the data warehouse project's own responsibility —
it should publish that through the SAME catalogue mechanism (or an
equivalent one Report Builder can consume generically), not have Report
Builder reach in and introspect its internals directly.

Best-effort: any lookup failure (datamart unreachable, tenant not yet
provisioned, ...) yields an empty reference rather than failing the chat
turn — the AI just asks instead of guessing.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.services.semantic_service import SemanticService

log = get_logger(__name__)


def build_catalogue_reference(db: Session, tenant_id: str) -> str:
    """A compact 'schema.table: column — label' listing of the curated field
    catalogue, grouped by table and deduped, for prompt grounding."""
    try:
        catalog = SemanticService(db).get_active_catalog(tenant_id)
    except Exception as exc:  # noqa: BLE001 - grounding is best-effort, never fatal to a chat turn
        log.warning("rule_chat_mart_reference_failed", tenant_id=tenant_id, error=str(exc)[:200])
        return ""
    ref = format_catalogue_reference(catalog)
    if not ref:
        log.warning("rule_chat_mart_reference_empty", tenant_id=tenant_id, entities=len(catalog.entities))
    return ref


def format_catalogue_reference(catalog) -> str:
    """Pure formatting step, split out from the DB-touching lookup above so it's
    unit-testable without a live SemanticService/session."""
    by_table: dict[str, dict[str, str]] = {}
    for entity in catalog.entities:
        for field in entity.fields:
            schema_name = field.physical.schema_name or entity.base_schema
            table_key = f"{schema_name}.{field.physical.table}"
            by_table.setdefault(table_key, {})[field.physical.column] = field.label

    if not by_table:
        return ""

    lines = [
        ("Known physical tables/columns in THIS tenant's datamart (from the governed "
         "field catalogue — use these exact schema.table and column names; if what "
         "you need isn't listed here, ASK the analyst rather than inventing a name):"),
    ]
    for table_key in sorted(by_table):
        lines.append(f"\n{table_key}:")
        for column, label in sorted(by_table[table_key].items()):
            lines.append(f"  {column} — {label}")
    return "\n".join(lines)
