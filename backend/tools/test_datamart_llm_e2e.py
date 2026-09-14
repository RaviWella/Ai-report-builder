"""Smoke test: datamart LLM uses hosted ai-core (mint-analytics pattern)."""
from __future__ import annotations

import os
import sys

from app.services.ai_services.datamart.llm.llm_client import (
    LlmRole,
    call_llm,
    clear_llm_cache,
    sync_process_openai_api_key,
)
from app.services.ai_services.datamart.llm.llm_settings import resolve_llm_connection


def main() -> int:
    clear_llm_cache()
    sync_process_openai_api_key()
    conn = resolve_llm_connection("gpt-oss:20b")
    print(f"backend={conn.backend} model={conn.model} base={conn.base_url} auth={bool(conn.auth_headers)}")
    if os.environ.get("OPENAI_API_KEY"):
        print("WARN: OPENAI_API_KEY still set in process")

    try:
        text = call_llm(
            "You reply with one word only.",
            "Reply exactly: OK",
            role=LlmRole.CHAT,
        )
    except Exception as exc:
        msg = str(exc)
        if "pBDj" in msg or "p0Dj" in msg or "token_not_found" in msg:
            print("FAIL: still using Minchy proxy / stale OPENAI_API_KEY")
        print(f"FAIL: {msg[:400]}")
        return 1

    print(f"OK: call_llm returned {len(text)} chars, preview={text[:60]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
