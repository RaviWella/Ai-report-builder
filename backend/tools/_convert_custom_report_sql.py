"""One-off: convert dbt custom_reports SQL to app token SQL (migration seed data)."""
from __future__ import annotations

import re
from pathlib import Path

DBT = Path(__file__).resolve().parent.parent / "dbt_project/hr_mart/models/custom_reports"
OUT = Path(__file__).resolve().parent.parent / "alembic/data/custom_report_sql"

STAGING = frozenset({"stg_processed_sal_attendance", "stg_processed_prl_overtime"})


def convert(content: str) -> str:
    lines = []
    skip_config = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("{{ config"):
            skip_config = True
            continue
        if skip_config:
            if stripped.endswith(") }}"):
                skip_config = False
            continue
        lines.append(line)
    text = "\n".join(lines)

    def repl_ref(match: re.Match[str]) -> str:
        name = match.group(1)
        schema = "{raw_schema}" if name in STAGING else "{mart_schema}"
        return f"{schema}.{name}"

    text = re.sub(r"\{\{\s*ref\('([^']+)'\)\s*\}\}", repl_ref, text)
    text = re.sub(r"'\{\{\s*var\(['\"]tenant_id['\"]\)\s*\}\}'", "'{tenant_id}'", text)
    text = re.sub(r"\{\{\s*var\(['\"]tenant_id['\"]\)\s*\}\}", "'{tenant_id}'", text)
    return text.strip()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for src in sorted(DBT.glob("*.sql")):
        dest = OUT / src.name
        dest.write_text(convert(src.read_text(encoding="utf-8")), encoding="utf-8")
        print(f"{src.name} -> {len(dest.read_text(encoding='utf-8'))} chars")


if __name__ == "__main__":
    main()
