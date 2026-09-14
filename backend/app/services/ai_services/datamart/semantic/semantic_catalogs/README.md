# Per-tenant semantic catalogs (Phase 11)

Each ETL tenant gets `semantic_catalogs/{tenant_id}.yaml`, generated from the live
`hrm_wh_*` warehouse (`hr_semantic`, `hr`, `hr_snap`).

Generate or refresh (from `backend/`):

```bash
python tools/semantic_catalog_tool.py refresh --tenant demo_tenant --dry-run
python tools/semantic_catalog_tool.py refresh --tenant demo_tenant --write
python tools/semantic_catalog_tool.py validate --tenant demo_tenant
```

Or via repo script:

```powershell
.\scripts\refresh_datamart_metadata.ps1 -TenantEtl -TenantId demo_tenant
```

Legacy `../semantic_catalog.yaml` remains for `legacy_audit` profile only.

## Row versioning (`is_current`)

Many `hr` mart tables are SCD-style: several rows per employee/entity, with
`is_current = TRUE` on the latest version. Datamart chat applies an automatic
`alias.is_current IS TRUE` filter for **current-state** questions (see
`is_current_policy.py`); historical / as-of questions should use explicit wording
or `hr_snap.snap_*` tables so older versions are included.
