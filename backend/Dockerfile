FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# packages.yml deps are gitignored; install at image build for ETL/dbt transforms
RUN cd dbt_project/hr_mart && dbt deps

RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

# Migrations run once in docker-entrypoint.sh (RUN_MIGRATIONS_IN_ENTRYPOINT); lifespan skips Alembic.
HEALTHCHECK --interval=15s --timeout=5s --start-period=90s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]
