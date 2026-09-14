#!/bin/sh
set -eu
cd /app

echo "==> MintHRM backend entrypoint"

# Platform DB migrations (hrm_control). Warehouse DDL is per-tenant at runtime.
# RUN_MIGRATIONS_IN_ENTRYPOINT — Docker/CI only (default true). Do not use RUN_MIGRATIONS_ON_STARTUP here.
_entrypoint_migrated=false
if [ "${RUN_MIGRATIONS_IN_ENTRYPOINT:-true}" != "false" ] && [ "${RUN_MIGRATIONS_IN_ENTRYPOINT:-true}" != "0" ]; then
  echo "==> Running Alembic migrations (alembic upgrade head)…"
  if ! alembic upgrade head; then
    echo "ERROR: Alembic upgrade failed — container will not start"
    exit 1
  fi
  echo "==> Alembic migrations complete"
  _entrypoint_migrated=true
else
  echo "==> RUN_MIGRATIONS_IN_ENTRYPOINT disabled — skipping entrypoint migrations"
fi

# Prevent duplicate Alembic run in FastAPI lifespan (see app/main.py).
if [ "${_entrypoint_migrated}" = "true" ]; then
  export RUN_MIGRATIONS_ON_STARTUP=false
fi

# packages.yml deps are gitignored; bind mounts hide image-built dbt_packages.
if [ "${SKIP_DBT_DEPS_ON_STARTUP:-false}" != "true" ] && [ "${SKIP_DBT_DEPS_ON_STARTUP:-false}" != "1" ]; then
  if [ ! -d /app/dbt_project/hr_mart/dbt_packages/dbt_utils ]; then
    echo "==> Installing dbt packages (dbt deps)…"
    if ! (cd /app/dbt_project/hr_mart && dbt deps); then
      echo "ERROR: dbt deps failed — ETL transforms will not run until packages install"
      exit 1
    fi
    echo "==> dbt packages ready"
  else
    echo "==> dbt packages already present"
  fi
else
  echo "==> SKIP_DBT_DEPS_ON_STARTUP set — skipping dbt deps"
fi

echo "==> Starting API (uvicorn)…"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
