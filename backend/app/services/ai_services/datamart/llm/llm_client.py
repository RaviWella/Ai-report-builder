"""LangChain LLM client with per-role model selection."""
from __future__ import annotations

import hashlib
import logging
import os
import re
from enum import Enum

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ..config import (
    DATAMART_CHAT_MODEL,
    DATAMART_REPAIR_MODEL,
    DATAMART_TEMPLATE_MODEL,
)
from .llm_settings import (
    LlmConnection,
    effective_minchy_api_key,
    experience_llm_backend,
    resolve_llm_connection,
)
from .prompt_budget import estimate_tokens, is_context_length_error

logger = logging.getLogger("ai_services.datamart.llm")

_llm_by_key: dict[str, ChatOpenAI] = {}


class LlmRole(str, Enum):
    CHAT = "chat"
    TEMPLATE = "template"
    REPAIR = "repair"


_MODEL_BY_ROLE: dict[LlmRole, str] = {
    LlmRole.CHAT: DATAMART_CHAT_MODEL,
    LlmRole.TEMPLATE: DATAMART_TEMPLATE_MODEL,
    LlmRole.REPAIR: DATAMART_REPAIR_MODEL,
}


def clear_llm_cache() -> None:
    """Drop cached clients (e.g. after .env change or uvicorn reload)."""
    _llm_by_key.clear()


def _cache_key(conn: LlmConnection) -> str:
    hdr_fp = hashlib.sha256(repr(sorted(conn.auth_headers.items())).encode()).hexdigest()[:8]
    key_fp = hashlib.sha256(conn.api_key.encode()).hexdigest()[:12]
    return f"{conn.backend}|{conn.base_url}|{conn.model}|{conn.user}|{key_fp}|{hdr_fp}"


def _strip_stale_openai_env() -> str | None:
    """Remove a user-level OPENAI_API_KEY that would override explicit client credentials."""
    prior = os.environ.get("OPENAI_API_KEY")
    if not prior:
        return None
    minchy = effective_minchy_api_key()
    if experience_llm_backend() == "ollama":
        os.environ.pop("OPENAI_API_KEY", None)
        return prior
    if minchy and prior != minchy:
        os.environ["OPENAI_API_KEY"] = minchy
        return prior
    return prior


def sync_process_openai_api_key() -> None:
    """Align or clear process OPENAI_API_KEY so LangChain cannot use a stale user key."""
    backend = experience_llm_backend()
    if backend == "ollama":
        stale = (os.environ.get("OPENAI_API_KEY") or "").strip()
        if stale:
            logger.warning(
                "Clearing process OPENAI_API_KEY (suffix …%s) — datamart uses hosted Ollama",
                stale[-4:],
            )
        os.environ.pop("OPENAI_API_KEY", None)
        return

    key = effective_minchy_api_key()
    if not key:
        return
    env_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if env_key and env_key != key:
        logger.warning(
            "Replacing process OPENAI_API_KEY (suffix …%s) with Minchy key from backend/.env (…%s)",
            env_key[-4:],
            key[-4:],
        )
    os.environ["OPENAI_API_KEY"] = key


def _build_chat_openai(conn: LlmConnection) -> ChatOpenAI:
    if conn.backend == "minchy" and not conn.api_key:
        raise ValueError("Minchy API key is empty — check AI_PROXY_API_KEY in backend/.env")

    base_url = conn.base_url.rstrip("/")
    default_headers = dict(conn.auth_headers) if conn.auth_headers else None

    timeout_sec = 180
    kwargs: dict = {
        "model": conn.model,
        "temperature": 0,
        "api_key": conn.api_key,
        "base_url": base_url,
        "timeout": timeout_sec,
        "max_retries": 1,
        "model_kwargs": {"user": conn.user},
    }
    if default_headers:
        kwargs["default_headers"] = default_headers
    kwargs["openai_api_key"] = conn.api_key
    kwargs["openai_api_base"] = base_url

    _strip_stale_openai_env()
    return ChatOpenAI(**kwargs)


def get_llm(role: LlmRole = LlmRole.CHAT) -> ChatOpenAI:
    model = _MODEL_BY_ROLE[role]
    conn = resolve_llm_connection(model)
    key = _cache_key(conn)
    if key not in _llm_by_key:
        _llm_by_key[key] = _build_chat_openai(conn)
        logger.info(
            "Datamart LLM client: role=%s backend=%s model=%s base=%s",
            role.value,
            conn.backend,
            conn.model,
            conn.base_url,
        )
    return _llm_by_key[key]


def coerce_llm_text(content: object) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text") or block.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return str(content)


def strip_reasoning_artifacts(text: str) -> str:
    _reasoning_open = "<" + "redacted_reasoning" + ">"
    _reasoning_close = "</" + "redacted_reasoning" + ">"
    text = re.sub(
        re.escape(_reasoning_open) + r"[\s\S]*?" + re.escape(_reasoning_close),
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"<think(?:ing)?>[\s\S]*?</think(?:ing)?>", "", text, flags=re.IGNORECASE)
    return text.strip()


def call_llm(
    system: str,
    user: str,
    *,
    role: LlmRole = LlmRole.CHAT,
) -> str:
    _strip_stale_openai_env()
    llm = get_llm(role)
    try:
        response = llm.invoke([
            SystemMessage(content=system),
            HumanMessage(content=user),
        ])
    except Exception as exc:  # noqa: BLE001
        if is_context_length_error(exc):
            logger.error(
                "LLM context length exceeded (role=%s est_user_tokens=%d): %s",
                role.value,
                estimate_tokens(user),
                exc,
            )
        raise
    return strip_reasoning_artifacts(coerce_llm_text(response.content))
