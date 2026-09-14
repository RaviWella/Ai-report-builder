"""Find source DB column/table for JE labels."""
from __future__ import annotations

import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

JE_LABELS = [
    "Admin",
    "BIA - Admin",
    "Director",
    "Factory Staff - indirect",
    "Packing Assistance",
    "Production Staff - Direct",
]


def main() -> int:
    host = os.getenv("MYSQL_HOST")
    if not host:
        print("MYSQL_HOST not set")
        return 1

    url = (
        f"mysql+pymysql://{os.getenv('MYSQL_USER')}:{os.getenv('MYSQL_PASSWORD')}"
        f"@{host}:{os.getenv('MYSQL_PORT', '3306')}/{os.getenv('MYSQL_DB')}"
    )
    src = create_engine(url)

    with src.connect() as conn:
        print("=== company_hierarchy: exact name matches ===")
        rows = conn.execute(
            text(
                """
                SELECT id, hierarchy_section_code, hierarchy_section_name,
                       parent_id, ref_leader_id
                FROM company_hierarchy
                WHERE hierarchy_section_name IN :labels
                ORDER BY hierarchy_section_name
                """
            ),
            {"labels": tuple(JE_LABELS)},
        ).fetchall()
        if rows:
            for r in rows:
                print(f"  id={r[0]}, code={r[1]!r}, name={r[2]!r}, parent_id={r[3]}")
        else:
            print("  (no exact matches)")

        print("\n=== company_hierarchy: fuzzy matches ===")
        for label in JE_LABELS:
            rows = conn.execute(
                text(
                    """
                    SELECT id, hierarchy_section_name, parent_id
                    FROM company_hierarchy
                    WHERE hierarchy_section_name LIKE :pat
                    ORDER BY hierarchy_section_name
                    LIMIT 5
                    """
                ),
                {"pat": f"%{label}%"},
            ).fetchall()
            print(f"  LIKE %{label}%:")
            for r in rows:
                print(f"    id={r[0]}, name={r[1]!r}, parent_id={r[2]}")

        print("\n=== Parent nodes whose children exist (JE roll-up check) ===")
        rows = conn.execute(
            text(
                """
                SELECT
                    p.id AS parent_id,
                    p.hierarchy_section_name AS parent_name,
                    COUNT(c.id) AS child_count
                FROM company_hierarchy p
                INNER JOIN company_hierarchy c ON c.parent_id = p.id
                WHERE p.hierarchy_section_name IN :labels
                GROUP BY p.id, p.hierarchy_section_name
                ORDER BY p.hierarchy_section_name
                """
            ),
            {"labels": tuple(JE_LABELS)},
        ).fetchall()
        for r in rows:
            print(f"  parent_id={r[0]}, parent_name={r[1]!r}, children={r[2]}")

        print("\n=== Sample employees mapped to these JE parents ===")
        rows = conn.execute(
            text(
                """
                SELECT
                    p.hierarchy_section_name AS je_name,
                    c.hierarchy_section_name AS employee_section_name,
                    COUNT(DISTINCT emp.ref_emp_id) AS emp_count
                FROM company_hierarchy c
                INNER JOIN company_hierarchy p ON p.id = c.parent_id
                INNER JOIN hr_employment emp ON emp.emp_section_id = c.id
                WHERE p.hierarchy_section_name IN :labels
                GROUP BY p.hierarchy_section_name, c.hierarchy_section_name
                ORDER BY p.hierarchy_section_name, emp_count DESC
                LIMIT 30
                """
            ),
            {"labels": tuple(JE_LABELS)},
        ).fetchall()
        for r in rows:
            print(f"  JE={r[0]!r} <- section={r[1]!r} ({r[2]} employees)")

        print("\n=== Other tables/columns containing these strings ===")
        tables = conn.execute(
            text(
                """
                SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND DATA_TYPE IN ('varchar', 'char', 'text', 'mediumtext', 'longtext')
                ORDER BY TABLE_NAME, ORDINAL_POSITION
                """
            )
        ).fetchall()

        hits: list[tuple[str, str, str]] = []
        for table, column, _dtype in tables:
            t, c = table, column
            try:
                found = conn.execute(
                    text(
                        f"""
                        SELECT DISTINCT `{c}`
                        FROM `{t}`
                        WHERE `{c}` IN :labels
                        LIMIT 20
                        """
                    ),
                    {"labels": tuple(JE_LABELS)},
                ).fetchall()
                for row in found:
                    if row[0]:
                        hits.append((t, c, str(row[0])))
            except Exception:
                continue

        if hits:
            by_col: dict[tuple[str, str], list[str]] = {}
            for t, c, v in hits:
                by_col.setdefault((t, c), []).append(v)
            for (t, c), vals in sorted(by_col.items()):
                print(f"  {t}.{c}: {vals}")
        else:
            print("  (no exact matches outside company_hierarchy)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
