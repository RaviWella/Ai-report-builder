# HR datamart documentation

Architecture diagrams and ER references for the tenant warehouse (`hrm_wh_{tenant_id}`).

## Files

| File | Purpose |
|------|---------|
| [`datamart-er.yml`](datamart-er.yml) | **Source of truth** — domains, relationships, semantic views, PK/grain overrides |
| [`leave-intelligence-mart-design.md`](leave-intelligence-mart-design.md) | **Leave mart design** — source mapping, phases 0–4 (implemented), future modules |
| [`HR_DATAMART_ER.pdf`](HR_DATAMART_ER.pdf) | Shareable PDF (generated; commit when sharing externally) |
| [`DATA_DICTIONARY.md`](DATA_DICTIONARY.md) | Enterprise data dictionary index (tables, metrics, lineage) |
| [`hr-datamart-er.html`](hr-datamart-er.html) | Printable HTML (auto-generated with PDF) |

Interactive Canvas (Cursor IDE only):  
`~/.cursor/projects/e-mint-analytics-mint-hrm/canvases/hr-datamart-er.canvas.tsx`

## When to update (required)

Update documentation whenever you make a **structural** change to datamarts, including:

- Add, rename, or remove a dbt model under `backend/dbt_project/hr_mart/models/marts/` or `models/semantic/`
- Change fact grain or primary surrogate key (`*_sk`)
- Add or remove FK-style joins between facts/marts and dimensions
- Add or change a semantic view (`vw_*`) or what it reads from

**Not required** for column-only changes inside an existing table (unless grain or PK changes).

## How to update

1. Edit [`datamart-er.yml`](datamart-er.yml):
   - `domain_models` — list of model names per domain
   - `relationships` — `from` / `to` / `label` edges
   - `semantic_views` — view name and upstream description
   - `model_meta` — optional `pk`, `grain`, `kind` overrides
2. Validate against dbt on disk:

   ```powershell
   python backend/tools/generate_hr_er_pdf.py --check
   ```

3. Regenerate the PDF and HTML:

   ```powershell
   python backend/tools/generate_hr_er_pdf.py
   ```

4. Commit **`datamart-er.yml`**, **`HR_DATAMART_ER.pdf`**, and **`hr-datamart-er.html`** together with your dbt/ETL changes (same PR).

## Data dictionary

Regenerate the full markdown data dictionary from the live warehouse + dbt metadata:

```powershell
cd backend
$env:PYTHONPATH="."
python tools/generate_data_dictionary.py --tenant demo_tenant
```

Outputs under `docs/` — see [DATA_DICTIONARY.md](DATA_DICTIONARY.md).

The same field catalog is stored in the warehouse (`hr_control.data_dictionary_*`) and exposed as `hr_semantic.vw_data_dictionary` when you run the generator (default).

## PR checklist

- [ ] dbt models changed → `datamart-er.yml` updated
- [ ] `python backend/tools/generate_hr_er_pdf.py --check` passes
- [ ] PDF regenerated if sharing with stakeholders
