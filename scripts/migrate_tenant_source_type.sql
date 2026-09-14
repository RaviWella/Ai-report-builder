-- Add dynamic source type to tenant registry (run once on warehouse Postgres).
ALTER TABLE hrm_control.tenant_registry
    ADD COLUMN IF NOT EXISTS source_type VARCHAR(16) NOT NULL DEFAULT 'mysql';

COMMENT ON COLUMN hrm_control.tenant_registry.source_type IS
    'ETL source database: mysql | postgres. Connection fields remain in mysql_* columns.';
