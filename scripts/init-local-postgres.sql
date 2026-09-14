-- MintHRM — local PostgreSQL init (run: python scripts/apply_init.py)

CREATE SCHEMA IF NOT EXISTS hrm_control;

CREATE TABLE IF NOT EXISTS hrm_control.tenant_registry (
    tenant_id       VARCHAR(64) PRIMARY KEY,
    display_name    VARCHAR(255),
    source_type     VARCHAR(16) NOT NULL DEFAULT 'mysql',
    mysql_host      VARCHAR(255),
    mysql_port      INTEGER DEFAULT 3306,
    mysql_db        VARCHAR(255),
    mysql_user      VARCHAR(255),
    mysql_password_enc TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    last_etl_at     TIMESTAMPTZ
);
