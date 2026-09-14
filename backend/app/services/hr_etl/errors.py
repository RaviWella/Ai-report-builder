"""Normalize ETL exceptions for run logs and API responses."""
from __future__ import annotations

import traceback
from typing import Any, Optional


def format_run_error(exc: BaseException, *, include_traceback: bool = False) -> str:
    """Human-readable error text; never returns an empty string."""
    parts: list[str] = []
    name = type(exc).__name__
    text = str(exc).strip()

    if text:
        parts.append(text)
    else:
        parts.append(name)

    cause = exc.__cause__ or exc.__context__
    if cause and cause is not exc:
        cause_text = str(cause).strip() or type(cause).__name__
        parts.append(f"Caused by: {cause_text}")

    if name == "InvalidToken" or "InvalidToken" in name:
        parts.append(
            "Stored database credentials could not be decrypted. "
            "Ensure DB_ENCRYPTION_KEY in backend/.env matches the key used when "
            "the source was saved, or re-enter the password under Settings → ETL Sources."
        )

    message = " ".join(parts).strip()
    if include_traceback:
        tb = traceback.format_exc(limit=8)
        if tb and tb.strip() != "NoneType: None\n":
            message = f"{message}\n\n{tb}"
    return message[:2000] if message else "ETL failed (no error detail; check API server logs)."


def run_error_payload(
    error_message: str,
    *,
    exc: Optional[BaseException] = None,
    error_code: Optional[str] = None,
) -> dict[str, Any]:
    """Structured failure object for status APIs (RFC 9457–style, simplified)."""
    detail = (error_message or "").strip()
    if not detail and exc is not None:
        detail = format_run_error(exc)
    if not detail:
        detail = "ETL failed with no error message recorded."
    code = error_code or (type(exc).__name__ if exc else "ETL_RUN_FAILED")
    return {
        "type": f"urn:mint-hrm:etl:{code}",
        "title": "ETL run failed",
        "detail": detail,
        "status": 500,
    }
