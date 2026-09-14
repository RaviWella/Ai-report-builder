"""Resolve datamart LLM endpoint from MintHRM settings (hosted Ollama vs Minchy proxy)."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field

from app.core.config import settings

logger = logging.getLogger("ai_services.datamart.llm")

_PLACEHOLDER_KEYS = frozenset(
    {
        "",
        "your_minchy_api_key",
        "changeme",
        "sk-placeholder",
        "open-ai-api-key",
    }
)


@dataclass(frozen=True)
class LlmConnection:
    backend: str
    base_url: str
    api_key: str
    model: str
    user: str
    auth_headers: dict[str, str] = field(default_factory=dict)


def _clean_api_key(raw: str | None) -> str:
    key = (raw or "").strip()
    if not key or key.lower() in _PLACEHOLDER_KEYS or key.startswith("your_"):
        return ""
    return key


def effective_minchy_api_key() -> str:
    """Minchy proxy token from .env only (never os.environ OPENAI_API_KEY)."""
    return _clean_api_key(getattr(settings, "AI_PROXY_API_KEY", "")) or _clean_api_key(
        getattr(settings, "MINCHY_AI_API_KEY", "")
    )


def experience_llm_backend() -> str:
    """
    Default to hosted Ollama on ai-core (same as working local datamart).

    Production often sets MINCHY_AI_API_KEY from an old template while chat actually
    needs OLLAMA_URL + OLLAMA_AUTH. When both are present, prefer Ollama unless
    EXPERIENCE_LLM_BACKEND=minchy is explicit.
    """
    explicit = (getattr(settings, "EXPERIENCE_LLM_BACKEND", "") or "").strip().lower()
    ollama_url = (getattr(settings, "OLLAMA_URL", "") or "").lower()
    has_ollama_auth = bool((getattr(settings, "OLLAMA_AUTH", "") or "").strip())
    hosted_ai_core = "ai-core.minchy.ai" in ollama_url

    if explicit == "minchy":
        return "minchy"
    if explicit == "ollama":
        return "ollama"
    if has_ollama_auth or hosted_ai_core:
        return "ollama"
    if effective_minchy_api_key():
        return "minchy"
    return "ollama"


def effective_model_for_backend(backend: str, requested: str) -> str:
    """
    Map DATAMART_* model names to what each backend accepts.

    ai-core Ollama uses tags like ``gpt-oss:20b``. Minchy LiteLLM proxy typically
    expects ``gpt-oss`` / ``MINCHY_AI_MODEL`` without an Ollama-style ``:tag``.
    """
    from .. import config as dm_config

    req = (requested or "").strip()
    chat_model = (dm_config.DATAMART_CHAT_MODEL or "").strip()
    if backend == "ollama":
        ollama_default = (
            chat_model
            or os.getenv("DATAMART_OLLAMA_MODEL", "").strip()
            or getattr(settings, "OLLAMA_MODEL", "")
            or getattr(settings, "EXPERIENCE_LLM_MODEL", "")
            or "gpt-oss:20b"
        )
        if not req:
            return ollama_default
        # Bare gpt-oss 404s on ai-core Ollama; prefer tagged env or default tag.
        if req == "gpt-oss":
            if ":" in ollama_default:
                return ollama_default
            return "gpt-oss:20b"
        return req
    proxy_default = (
        getattr(settings, "MINCHY_AI_MODEL", "") or os.getenv("DATAMART_LLM_MODEL", "gpt-oss")
    ).strip()
    if not req:
        return proxy_default
    if ":" in req:
        return proxy_default or req.split(":", 1)[0]
    return req


def _ollama_auth_headers() -> dict[str, str]:
    auth = (getattr(settings, "OLLAMA_AUTH", "") or "").strip()
    if not auth:
        return {}
    return {"Authorization": f"Basic {auth}"}


def resolve_llm_connection(model: str) -> LlmConnection:
    """Pick hosted Ollama (ai-core) or Minchy proxy based on settings."""
    user = getattr(settings, "EXPERIENCE_LLM_USER", "mint-hrm-dev")
    backend = experience_llm_backend()

    if backend == "ollama":
        ollama_url = getattr(settings, "OLLAMA_URL", "http://localhost:11434").rstrip("/")
        ollama_model = effective_model_for_backend("ollama", model)
        return LlmConnection(
            backend="ollama",
            base_url=f"{ollama_url}/v1",
            api_key="ollama",
            model=ollama_model,
            user=user,
            auth_headers=_ollama_auth_headers(),
        )

    key = effective_minchy_api_key()
    if not key:
        raise ValueError(
            "Datamart LLM is not configured: set MINCHY_AI_API_KEY or AI_PROXY_API_KEY in "
            "backend/.env, or set EXPERIENCE_LLM_BACKEND=ollama with OLLAMA_URL / OLLAMA_AUTH."
        )

    base = getattr(settings, "MINCHY_AI_BASE_URL", "https://ai-proxy.minchy.ai").rstrip("/")
    proxy_model = effective_model_for_backend("minchy", model)
    return LlmConnection(
        backend="minchy",
        base_url=base,
        api_key=key,
        model=proxy_model,
        user=user,
    )


def format_llm_error(exc: Exception) -> tuple[str, str]:
    """User-facing narrative and error code for LLM failures."""
    msg = str(exc)
    lower = msg.lower()
    backend = experience_llm_backend()
    if (
        "401" in msg
        or "403" in msg
        or "authentication error" in lower
        or "token_not_found" in lower
        or "invalid proxy server token" in lower
        or "incorrect api key" in lower
    ):
        if backend == "minchy":
            hint = (
                "The Minchy AI proxy rejected the API key on the server. "
                "Set MINCHY_AI_API_KEY or AI_PROXY_API_KEY in production backend/.env, "
                "or use EXPERIENCE_LLM_BACKEND=ollama with OLLAMA_URL and OLLAMA_AUTH (same as local)."
            )
        else:
            hint = (
                "Could not authenticate to the hosted AI server. "
                "Set OLLAMA_URL, OLLAMA_MODEL, and OLLAMA_AUTH on the server (copy from working local backend/.env)."
            )
        return hint, "llm_auth_failed"
    if (
        "connection" in lower
        or "refused" in lower
        or "timeout" in lower
        or "timed out" in lower
        or "name or service not known" in lower
        or "certificate" in lower
        or "ssl" in lower
    ):
        return (
            "Could not connect to the AI service from the API server. "
            "Copy EXPERIENCE_LLM_BACKEND, OLLAMA_URL, OLLAMA_AUTH (or MINCHY_AI_*) from local backend/.env "
            "into production secrets and ensure outbound HTTPS to ai-core.minchy.ai / ai-proxy.minchy.ai is allowed.",
            "llm_connection_failed",
        )
    if (
        "model" in lower
        and ("not found" in lower or "does not exist" in lower or "unknown model" in lower)
    ) or ("404" in msg and "model" in lower):
        try:
            conn = resolve_llm_connection(os.getenv("DATAMART_CHAT_MODEL", "gpt-oss"))
            model_hint = conn.model
        except Exception:
            model_hint = os.getenv("DATAMART_CHAT_MODEL", "gpt-oss")
        hint = (
            f"The AI server does not expose model '{model_hint}'. "
            "Set DATAMART_CHAT_MODEL=gpt-oss:20b (or another tag from GET /api/tags on OLLAMA_URL) "
            "in backend/.env and restart the API."
        )
        if backend == "minchy" and ":" in model_hint:
            hint += (
                " For Minchy proxy use MINCHY_AI_MODEL=gpt-oss (no :tag), or set "
                "EXPERIENCE_LLM_BACKEND=ollama with OLLAMA_URL + OLLAMA_AUTH like local."
            )
        return hint, "llm_model_error"
    if "502" in msg or "503" in msg or "bad gateway" in lower or "service unavailable" in lower:
        return (
            "The AI service returned a temporary server error. Please retry in a moment. "
            "If this persists, check /health → datamart_llm on the API host.",
            "llm_upstream_error",
        )
    if "rate" in lower and "limit" in lower:
        return (
            "The AI service rate-limited this request. Please wait and try again.",
            "llm_rate_limited",
        )
    if "context length" in lower or "maximum context" in lower:
        return (
            "The question plus schema context is too large for the AI model. "
            "Try a shorter question or start a new session.",
            "llm_context_length",
        )
    if settings.DEBUG:
        return f"The AI service failed: {msg[:600]}", "llm_error"
    logger.error("Datamart LLM failure (backend=%s): %s", backend, msg[:800])
    return "The AI service is currently unavailable. Please try again later.", "llm_error"


def probe_datamart_llm(timeout_seconds: int = 12) -> dict[str, str]:
    """Connectivity + one-token chat check for /health (no secrets returned)."""
    try:
        model = os.getenv("DATAMART_CHAT_MODEL", "gpt-oss")
        conn = resolve_llm_connection(model)
    except ValueError as exc:
        return {"status": "not_configured", "detail": str(exc)}

    import requests

    base = conn.base_url.rstrip("/")
    headers = dict(conn.auth_headers)
    if conn.backend == "minchy" and conn.api_key:
        headers.setdefault("Authorization", f"Bearer {conn.api_key}")

    out: dict[str, str] = {
        "backend": conn.backend,
        "base_url": conn.base_url,
        "model": conn.model,
        "requested_model": model,
    }

    try:
        models_resp = requests.get(
            f"{base}/models",
            headers=headers or None,
            timeout=timeout_seconds,
        )
        out["models_http"] = str(models_resp.status_code)
    except Exception as exc:  # noqa: BLE001
        out["status"] = "error"
        out["detail"] = f"models: {exc}"[:300]
        return out

    if models_resp.status_code != 200:
        out["status"] = f"http_{models_resp.status_code}"
        return out

    chat_url = f"{base}/chat/completions"
    payload = {
        "model": conn.model,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_tokens": 8,
        "temperature": 0,
        "user": getattr(settings, "EXPERIENCE_LLM_USER", "mint-hrm-dev"),
    }
    try:
        chat_resp = requests.post(
            chat_url,
            headers={**(headers or {}), "Content-Type": "application/json"},
            json=payload,
            timeout=max(timeout_seconds, 25),
        )
        out["chat_http"] = str(chat_resp.status_code)
        if chat_resp.status_code == 200:
            out["status"] = "ok"
            return out
        out["status"] = f"chat_http_{chat_resp.status_code}"
        out["detail"] = (chat_resp.text or "")[:300]
        if conn.backend == "minchy" and ":" in model:
            out["hint"] = (
                "Set EXPERIENCE_LLM_BACKEND=ollama with OLLAMA_AUTH (local pattern), "
                "or MINCHY_AI_MODEL=gpt-oss without :tag."
            )
        return out
    except Exception as exc:  # noqa: BLE001
        out["status"] = "chat_error"
        out["detail"] = str(exc)[:300]
        return out


def log_llm_config_status() -> None:
    """Log once at startup which LLM backend datamart will use."""
    try:
        conn = resolve_llm_connection(os.getenv("DATAMART_CHAT_MODEL", "gpt-oss"))
        requested = os.getenv("DATAMART_CHAT_MODEL", "gpt-oss")
        logger.warning(
            "Datamart LLM ready: backend=%s model=%s (requested=%s) base=%s auth=%s",
            conn.backend,
            conn.model,
            requested,
            conn.base_url,
            bool(conn.auth_headers),
        )
        if conn.backend == "minchy" and ":" in requested:
            logger.warning(
                "Datamart: DATAMART_CHAT_MODEL=%s uses an Ollama tag; Minchy proxy uses model=%s. "
                "For production parity with local, set EXPERIENCE_LLM_BACKEND=ollama + OLLAMA_AUTH.",
                requested,
                conn.model,
            )
    except ValueError as exc:
        logger.warning("Datamart LLM not configured: %s", exc)
