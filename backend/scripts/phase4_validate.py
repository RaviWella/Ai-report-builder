"""Phase 4 — AI assistant privacy-boundary validation (SRS §8, FR-A1..A7).

Proves WITHOUT a real provider:
  1. Excel ingestion strips ALL data rows before anything leaves the box — only
     headers + locally-inferred types remain (FR-A2, §8.2).
  2. The payload assembled for the AI is metadata-only: semantic refs/labels/types
     and the user's text — never physical column names, never employee data.
  3. AIService validates AI output against the Pydantic DataSpec + semantic guards,
     so a returned spec is trusted only after it resolves (FR-A6).

A FakeProvider captures exactly what the adapter would send and returns a canned
spec, so the full flow runs offline. Swap in the real provider with an API key for
the live round-trip (same interface — D9).
"""

from __future__ import annotations

import io

import pandas as pd

from app.ai.base import AIMappingResult, AIProvider, AISpecResult
from app.core.tenancy import TenantContext
from app.db.pg_tenant_session import init_postgres_tenant_session_manager, worker_pg_session
from app.db.postgres import init_postgres_database
from app.domain.enums import Role
from app.ingestion.excel_parser import parse_excel_headers
from app.services.ai_service import AIService

# A fake employee whose PII must NEVER appear in any AI payload.
SECRET_NAME = "Nimal Perera"
SECRET_NIC = "892345678V"
SECRET_SALARY = 999999


class FakeProvider(AIProvider):
    """Captures what the adapter passes in; returns a canned valid spec."""

    def __init__(self) -> None:
        self.captured: dict = {}

    def natural_language(self, request, fields):
        self.captured = {"request": request, "fields": [f.__dict__ for f in fields]}
        return AISpecResult(
            data_spec={
                "entity": "employee",
                "fields": [{"ref": "employee.employment_type", "label": "Type"}],
                "aggregations": [{"ref": "employee.headcount", "fn": "count", "label": "Headcount"}],
                "group_by": ["employee.employment_type"],
            },
            rationale="canned",
        )

    def adjustment_chat(self, instruction, current_spec, fields):
        self.captured = {"instruction": instruction, "current_spec": current_spec}
        return AISpecResult(data_spec=current_spec, rationale="canned")

    def excel_mapping(self, columns, fields):
        self.captured = {"columns": [c.__dict__ for c in columns]}
        return AIMappingResult(mappings=[], rationale="canned")


def main() -> None:
    print("=" * 64)
    print("1. EXCEL INGESTION — rows stripped before any AI call (FR-A2)")
    print("=" * 64)
    # A sample sheet a client might upload — WITH real-looking PII data rows.
    df = pd.DataFrame(
        {
            "Employee Name": [SECRET_NAME, "Kamala Silva"],
            "NIC": [SECRET_NIC, "907654321V"],
            "Department": ["Engineering", "Finance"],
            "Basic Salary": [SECRET_SALARY, 120000],
            "Join Date": ["2021-03-01", "2019-07-15"],
        }
    )
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    raw = buf.getvalue()

    parsed = parse_excel_headers(raw)
    print(f"  uploaded sheet had {parsed.row_count_seen} data rows")
    print("  parser output (this is ALL that can go onward):")
    for c in parsed.columns:
        print(f"     header={c.header!r:24} type={c.inferred_type}")
    blob = str([(c.header, c.inferred_type) for c in parsed.columns])
    assert SECRET_NAME not in blob and SECRET_NIC not in blob and str(SECRET_SALARY) not in blob
    print("  ✅ no PII values present — only headers + locally-inferred types")

    init_postgres_database()
    init_postgres_tenant_session_manager()
    tenant_id = "demo_tenant"
    with worker_pg_session(tenant_id) as db:
        ctx = TenantContext(
            tenant_id=tenant_id,
            pg_schema=tenant_id,
            acting_user_id="u1",
            role=Role.CLIENT_HR_ADMIN,
            on_behalf=False,
        )

        print()
        print("=" * 64)
        print("2. EXCEL-MAPPING payload to the AI is metadata-only (FR-A1)")
        print("=" * 64)
        fake = FakeProvider()
        ai = AIService(db, provider=fake)
        ai.map_excel(ctx, raw)
        sent = str(fake.captured)
        print("  adapter received (columns):", fake.captured["columns"])
        assert SECRET_NAME not in sent and SECRET_NIC not in sent and str(SECRET_SALARY) not in sent
        print("  ✅ PII never reached the provider boundary")

        print()
        print("=" * 64)
        print("3. NL request -> metadata-only fields -> validated data_spec (FR-A3/A6)")
        print("=" * 64)
        fake2 = FakeProvider()
        ai2 = AIService(db, provider=fake2)
        proposal = ai2.from_natural_language(ctx, "headcount by employment type")
        sample_fields = fake2.captured["fields"][:3]
        print("  metadata sent to AI (sample):")
        for f in sample_fields:
            print(f"     {f['ref']:30} {f['type']:8} {f['role']}")
        payload = str(fake2.captured["fields"])
        # The metadata-only projection must NOT leak physical table/column names.
        for phys in ("mart_employee_current", "vw_payroll_summary", "designation_department", "emp_fullname"):
            assert phys not in payload, f"LEAK: {phys}"
        print("  ✅ no physical table/column names in the AI payload")
        print("  validated spec entity:", proposal.data_spec.entity,
              "| fields:", [f.ref for f in proposal.data_spec.fields],
              "| aggs:", [(a.ref, a.fn.value) for a in proposal.data_spec.aggregations])
        print("  ✅ AI output passed Pydantic + semantic guards -> trusted")

    print("\n✅ PHASE 4 PRIVACY BOUNDARY VERIFIED: no PII, no SQL crosses the AI Adapter.")


if __name__ == "__main__":
    main()
