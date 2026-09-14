# MintHRM Report Builder — backend image (Architecture §9)
FROM python:3.13-slim AS base

# WeasyPrint native deps (HTML/CSS -> PDF) + build essentials for psycopg.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libffi-dev libcairo2 \
    fonts-dejavu-core fonts-noto-core curl ca-certificates \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# --- Claude Code CLI (AI-assisted rule-report builder) ---
# Node.js 22 + Claude Code CLI, on PATH for all users. Auth at runtime via
# CLAUDE_CODE_OAUTH_TOKEN (subscription login) or ANTHROPIC_API_KEY/_BASE_URL
# (proxy mode) — see app/services/rule_report_ai/runner.py.
# TARGETARCH is set automatically by BuildKit (amd64/arm64) — needed so this
# also builds on an Apple Silicon dev machine, not just the (amd64) deploy host.
ARG TARGETARCH
RUN case "$TARGETARCH" in \
      amd64) NODE_ARCH=x64 ;; \
      arm64) NODE_ARCH=arm64 ;; \
      *) echo "unsupported TARGETARCH: $TARGETARCH" >&2; exit 1 ;; \
    esac \
    && curl -fsSL "https://nodejs.org/dist/v22.17.1/node-v22.17.1-linux-${NODE_ARCH}.tar.gz" \
    | tar -xz --strip-components=1 -C /usr/local \
    && npm install -g @anthropic-ai/claude-code \
    && npm cache clean --force
# -----------------------------------------------

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
COPY docker-entrypoint.sh ./
RUN pip install --upgrade pip && pip install -e .
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["sh", "/app/docker-entrypoint.sh"]

# Production: Gunicorn managing Uvicorn workers (README §3.2).
# --timeout 300: the AI rule-report chat (rule_ai_max_turns=30, each turn
# potentially a real datamart tool call) can legitimately run well past
# gunicorn's old 120s default for a broad/exploratory request — that
# mismatch silently SIGABRT-killed the worker mid-request (gunicorn's
# WORKER TIMEOUT), surfacing to the user as a generic "couldn't reach the
# AI helper" with no useful error. 300s gives real headroom without
# masking a genuinely stuck request forever.
CMD ["gunicorn", "app.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "4", "-b", "0.0.0.0:8000", "--timeout", "300"]
