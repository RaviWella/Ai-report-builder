#!/bin/bash
# MintHRM — PostgreSQL init script (Docker)
# Creates application DB (hrm_platform) + hrm_control schema once at container init.
# Per-tenant warehouse DBs (hrm_wh_*) are NOT created here — app creates them when
# WAREHOUSE_AUTO_PROVISION=true (first ETL / tenant register). APP_AUTO_PROVISION=false.

set -e

APP_DB="${APP_DATABASE_NAME:-hrm_platform}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE ${APP_DB}'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${APP_DB}')\gexec
EOSQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$APP_DB" <<-EOSQL
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ai_reader') THEN
            CREATE ROLE ai_reader NOLOGIN;
        END IF;
    END
    \$\$;

    CREATE SCHEMA IF NOT EXISTS hrm_control;

    RAISE NOTICE 'MintHRM application database ${APP_DB} initialized.';
EOSQL
