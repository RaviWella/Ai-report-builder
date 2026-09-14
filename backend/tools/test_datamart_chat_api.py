"""HTTP smoke test for POST /api/v1/datamart/chat (server on :8000, DB + warehouse)."""
from __future__ import annotations

import sys

import httpx


def main() -> int:
    import os

    base = os.environ.get("DATAMART_TEST_BASE_URL", "http://127.0.0.1:8001")
    headers = {"X-API-Key": "hrm-dev-api-key"}
    payload = {
        "question": "How many rows exist in any one table? Reply in one short sentence only.",
    }

    try:
        resp = httpx.post(
            f"{base}/api/v1/datamart/chat",
            json=payload,
            headers=headers,
            timeout=180.0,
        )
    except httpx.ConnectError:
        print(f"FAIL: cannot reach {base} — start backend with .\\run-dev.ps1")
        return 1
    print("status", resp.status_code)
    if resp.status_code != 200:
        print(resp.text[:600])
        return 1

    body = resp.json()
    err = body.get("error") or ""
    narrative = (body.get("narrative") or "")[:200]
    if "401" in err or "token_not_found" in err or "Invalid proxy" in err:
        print("FAIL: auth error in response", err[:300])
        return 1
    if "llm_auth_failed" in str(body):
        print("FAIL: llm_auth_failed", body)
        return 1

    print("OK: session_id=", body.get("session_id"))
    print("narrative preview:", narrative)
    return 0


if __name__ == "__main__":
    sys.exit(main())
