# Tenant-specific source mapping overrides

Copy `example_tenant.yaml.example` to `{tenant_id}.yaml` and adjust only the
tables/columns that differ from `minthrm_mysql.yaml` or `minthrm_postgres.yaml`.

The merge is deep: you can override a single column without redefining the whole file.
