"""Source discovery / drill-down — "where does this data live, across every layer?"

The report layer only reads `mart_*` (join-safe, fast). But when a column a user
wants isn't in a mart, "not available" is a dead end. This service drills DOWN the
datamart's layers — marts → facts/dims → raw staging — to LOCATE the concept, say
which layer it's in, and give governed guidance ("exists in a fact, build a mart").

It is metadata-only and READ-ONLY: it reads `information_schema`, never guesses a
join, never fetches across irregular keys. So it can never produce wrong data — it
turns a blind "Request in data" into a precise, explained "here it is, here's how
to surface it".
"""

from __future__ import annotations

import difflib
import re

from sqlalchemy import text

from app.core.logging import get_logger
from app.db.datamart import get_datamart_engine

log = get_logger(__name__)

# Layers we drill through, top (report-ready) to bottom (raw). `mart` holds the
# denormalised report-ready tables; `core` holds the star schema (dims/facts).
_SCHEMAS = ["mart", "core"]

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _norm(s: str) -> str:
    return _NON_ALNUM.sub(" ", s.lower()).strip()


def _layer(table: str) -> tuple[str, int]:
    """(layer name, depth). Lower depth = closer to the report layer."""
    if table.startswith("mart_"):
        return "mart", 0
    if table.startswith(("fct_", "fact_")):
        return "fact", 1
    if table.startswith("dim_"):
        return "dimension", 1
    if table.startswith("stg_"):
        return "staging", 2
    return "other", 3


_GUIDANCE = {
    "mart": "Available now — this is a report mart; map to it directly.",
    "fact": "In a fact (grain-level). Build/extend a mart that joins it on the "
            "conformed key (employee_sk) to report on it.",
    "dimension": "In a dimension (lookup). Denormalise it into a mart, or join via "
                 "a conformed key.",
    "staging": "Only in raw staging — not yet modelled. Needs a fact/mart before it "
               "can be reported.",
}


class SourceDiscoveryService:
    """Locate a concept across the datamart's layers (metadata-only, read-only)."""

    def discover(self, datamart_key: str, term: str, limit: int = 10) -> dict:
        tn = _norm(term)
        if not tn:
            return {"term": term, "in_report_layer": False, "matches": [], "summary": "Empty search."}

        eng = get_datamart_engine(datamart_key)
        with eng.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            rows = conn.execute(
                text(
                    "SELECT table_schema, table_name, column_name FROM information_schema.columns "
                    "WHERE table_schema = ANY(:s)"
                ),
                {"s": _SCHEMAS},
            ).fetchall()

        # Best score per (schema.table.column); match on the column name.
        scored: dict[tuple[str, str, str], tuple[float, str, int]] = {}
        for schema, table, column in rows:
            layer, depth = _layer(table)
            if layer == "other":
                continue
            cn = _norm(column)
            if not cn:
                continue
            if tn == cn:
                score = 1.0
            # containment only when the shorter name is >=4 chars, so a 3-letter
            # column ("nic") can't spuriously match inside a word ("uNICorn").
            elif len(cn) >= 4 and len(tn) >= 4 and (tn in cn or cn in tn):
                score = 0.9
            else:
                score = difflib.SequenceMatcher(None, tn, cn).ratio()
            if score >= 0.55:
                key = (schema, table, column)
                if score > scored.get(key, (0.0,))[0]:
                    scored[key] = (score, layer, depth)

        ranked = sorted(
            ((k, v) for k, v in scored.items()),
            key=lambda kv: (-kv[1][0], kv[1][2]),  # score desc, then closer layer first
        )[:limit]

        matches = [
            {
                "schema": sch, "table": tbl, "column": col,
                "layer": layer, "score": round(score, 2),
                "guidance": _GUIDANCE.get(layer, ""),
            }
            for (sch, tbl, col), (score, layer, _depth) in ranked
        ]
        in_report = any(m["layer"] == "mart" for m in matches)

        if not matches:
            summary = f"'{term}' isn't captured anywhere in the datamart — a source-capture gap."
        elif in_report:
            summary = f"'{term}' is available in a report mart."
        else:
            top = matches[0]
            summary = (
                f"'{term}' isn't in a report mart, but it exists in "
                f"{top['schema']}.{top['table']}.{top['column']} ({top['layer']}) — "
                f"surface it via a mart to report on it."
            )
        log.info("source_discovery", datamart_key=datamart_key, term=term, matches=len(matches),
                 in_report=in_report)
        return {"term": term, "in_report_layer": in_report, "matches": matches, "summary": summary}

    def explain_gaps(self, datamart_key: str, terms: list[str]) -> list[dict]:
        """Business-language explanation of report gaps, for a chat with an HR user.
        For each term that isn't in a report mart: is it collected somewhere in the
        data (→ can be requested), or not captured at all? No technical names — the
        `fct_/dim_` detail is for the data team (Data Health), never shown to HR."""
        out: list[dict] = []
        for term in terms:
            r = self.discover(datamart_key, term, limit=3)
            if r["in_report_layer"]:
                continue  # actually available — not a gap
            if r["matches"]:
                out.append({
                    "term": term, "status": "in_source",
                    "message": f"“{term}” isn’t in your reports yet, but your system does "
                               f"collect it — it just needs to be added to your reports.",
                })
            else:
                out.append({
                    "term": term, "status": "not_captured",
                    "message": f"“{term}” isn’t being collected in your data yet.",
                })
        return out
