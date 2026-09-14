# MintHRM Data Dictionary

Generated from warehouse schema (`demo_tenant`) and dbt metadata.

**Last generated:** 2026-06-02 08:46 UTC  

## Regenerate

```powershell
cd backend
$env:PYTHONPATH="."
python tools/generate_data_dictionary.py --tenant demo_tenant
```

## Contents

| Document | Purpose |
|----------|---------|
| [warehouse_catalog.md](warehouse_catalog.md) | Full object inventory |
| [business_glossary.md](business_glossary.md) | Business terms |
| [metrics_dictionary.md](metrics_dictionary.md) | KPI definitions |
| [data_quality_rules.md](data_quality_rules.md) | Validation rules |
| [tables/](tables/) | Table-level documentation |
| [semantic/](semantic/) | Semantic view (`vw_*`) documentation |
| [lineage/](lineage/) | Source-to-target lineage by domain |

## Warehouse tables (SQL)

Field-level catalog is also stored in the tenant warehouse:

| Object | Schema | Purpose |
|--------|--------|---------|
| `data_dictionary_object` | `hr_control` | Table/view inventory |
| `data_dictionary_field` | `hr_control` | Column catalog (Field, Type, Nullable, PK, FK, Description, Source) |
| `vw_data_dictionary` | `hr_semantic` | Query-ready dictionary view |

```sql
SELECT field_name, data_type, nullable, pk, fk, description, source
FROM hr_semantic.vw_data_dictionary
WHERE object_name = 'fct_processed_salary'
ORDER BY ordinal_position;
```
