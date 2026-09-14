"""
Datamart AI Service — DataHub Integration
==========================================
Provides two public functions:

  search_relevant_tables(question)
      Extracts keywords from the user question and queries the DataHub
      GraphQL API for matching dataset URNs.

  get_columns_for_urns(urns)
      Fetches column-level metadata for a list of dataset URNs and
      returns a structured schema description ready for the LLM prompt.

Both functions are fault-tolerant: any DataHub connectivity issue is
logged and an empty result is returned so the agent can fall back to
direct database introspection.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional
from urllib.parse import urlparse

import requests

from .. import config as dh_config
from .datahub_scope import filter_urns_for_datamart_context
from ..config import (
    DATAHUB_GMS_URL,
    DATAHUB_TIMEOUT_SECONDS,
    MAX_CONTEXT_TABLES,
    MAX_SEARCH_KEYWORDS,
    SEARCH_STOP_WORDS,
    WAREHOUSE_SCHEMA,
)

logger = logging.getLogger("ai_services.datamart")

# After a failed GMS call, skip DataHub for this many seconds (avoids 5× timeout per question).
_DATAHUB_CIRCUIT_OPEN_UNTIL: float = 0.0
_DATAHUB_CIRCUIT_COOLDOWN_SEC: int = 60

# ── GraphQL query templates ───────────────────────────────────────

_SEARCH_QUERY = """
query SearchDatasets($input: SearchAcrossEntitiesInput!) {
  searchAcrossEntities(input: $input) {
    searchResults {
      entity {
        urn
        type
      }
    }
  }
}
"""

_DATASET_QUERY = """
query GetDataset($urn: String!) {
  dataset(urn: $urn) {
    name
    schemaMetadata {
      fields {
        fieldPath
        type
        description
      }
    }
  }
}
"""


# ── Helpers ───────────────────────────────────────────────────────

def _extract_keywords(question: str) -> list[str]:
    """
    Strip stop-words and punctuation from the question and return
    the top MAX_SEARCH_KEYWORDS meaningful tokens.
    """
    tokens = (
        question.lower()
        .replace("?", "")
        .replace(",", "")
        .replace(".", "")
        .split()
    )
    keywords = [t for t in tokens if t not in SEARCH_STOP_WORDS and len(t) > 2]
    return keywords[:MAX_SEARCH_KEYWORDS]


def datahub_request_headers() -> dict[str, str]:
    """Headers for GMS GraphQL; adds Bearer PAT when DATAHUB_GMS_TOKEN is set."""
    headers = {"Content-Type": "application/json"}
    token = (dh_config.DATAHUB_GMS_TOKEN or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _datahub_explicitly_enabled() -> bool:
    mode = (os.getenv("DATAMART_USE_DATAHUB", dh_config.DATAMART_USE_DATAHUB) or "auto").strip().lower()
    if mode in ("0", "false", "no", "off"):
        return False
    if mode in ("1", "true", "yes", "on"):
        return True
    # auto: skip default local quickstart URL unless a PAT is configured
    url = (os.getenv("DATAHUB_GMS_URL", DATAHUB_GMS_URL) or "").strip()
    token = (os.getenv("DATAHUB_GMS_TOKEN", dh_config.DATAHUB_GMS_TOKEN) or "").strip()
    if not url:
        return False
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host in ("localhost", "127.0.0.1") and not token:
        return False
    return True


def _open_datahub_circuit() -> None:
    global _DATAHUB_CIRCUIT_OPEN_UNTIL
    _DATAHUB_CIRCUIT_OPEN_UNTIL = time.time() + _DATAHUB_CIRCUIT_COOLDOWN_SEC


def _datahub_circuit_open() -> bool:
    return time.time() < _DATAHUB_CIRCUIT_OPEN_UNTIL


def _graphql_post(payload: dict) -> Optional[dict]:
    """
    Execute a GraphQL request against the DataHub GMS endpoint.
    Returns the parsed JSON body or None on any error.
    """
    try:
        response = requests.post(
            f"{DATAHUB_GMS_URL}/api/graphql",
            json=payload,
            headers=datahub_request_headers(),
            timeout=DATAHUB_TIMEOUT_SECONDS,
        )
        if response.status_code in (401, 403):
            logger.warning(
                "DataHub rejected credentials (HTTP %s). "
                "Set DATAHUB_GMS_TOKEN to a valid Personal Access Token.",
                response.status_code,
            )
            _open_datahub_circuit()
            return None
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        logger.warning("DataHub is not reachable at %s", DATAHUB_GMS_URL)
        _open_datahub_circuit()
    except requests.exceptions.Timeout:
        logger.warning("DataHub request timed out after %ds", DATAHUB_TIMEOUT_SECONDS)
        _open_datahub_circuit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("DataHub request failed: %s", exc)
        _open_datahub_circuit()
    return None


# ── Public API ────────────────────────────────────────────────────

def search_relevant_tables(question: str) -> list[str]:
    """
    Search DataHub for dataset URNs relevant to *question*.

    Performs one GraphQL search per extracted keyword and deduplicates
    results.  Returns a list of URN strings (may be empty).
    """
    if not _datahub_explicitly_enabled():
        return []
    if _datahub_circuit_open():
        return []

    keywords = _extract_keywords(question)
    if not keywords:
        return []

    logger.debug("DataHub search keywords: %s", keywords)

    seen: set[str] = set()
    urns: list[str] = []

    for keyword in keywords:
        data = _graphql_post({
            "query": _SEARCH_QUERY,
            "variables": {
                "input": {
                    "types": ["DATASET"],
                    "query": keyword,
                    "start": 0,
                    "count": 10,
                }
            },
        })

        if data is None:
            break

        if "errors" in data:
            continue

        results = (
            data.get("data", {})
            .get("searchAcrossEntities", {})
            .get("searchResults", [])
        )

        for item in results:
            urn = item.get("entity", {}).get("urn", "")
            if urn and urn not in seen:
                seen.add(urn)
                urns.append(urn)

        if len(urns) >= MAX_CONTEXT_TABLES:
            break

    filtered = filter_urns_for_datamart_context(urns)
    logger.debug(
        "DataHub returned %d unique URNs (%d after context filter)",
        len(urns),
        len(filtered),
    )
    return filtered[:MAX_CONTEXT_TABLES]


def get_columns_for_urns(urns: list[str]) -> str:
    """
    Fetch column metadata for each URN and return a formatted schema block.
    """
    if not urns or not _datahub_explicitly_enabled() or _datahub_circuit_open():
        return ""

    schema_parts: list[str] = []
    for urn in urns[:MAX_CONTEXT_TABLES]:
        data = _graphql_post({
            "query": _DATASET_QUERY,
            "variables": {"urn": urn},
        })
        if data is None:
            break
        if not data or "errors" in data:
            continue

        dataset = data.get("data", {}).get("dataset") or {}
        fields = dataset.get("schemaMetadata", {}).get("fields") or []
        if not fields:
            continue

        try:
            dataset_part = urn.split(",")[1]
            schema_table = ".".join(dataset_part.split(".")[-2:])
        except (IndexError, AttributeError):
            schema_table = dataset.get("name", urn)

        column_names = [f["fieldPath"] for f in fields if f.get("fieldPath")]
        col_list = ", ".join(column_names)
        schema_parts.append(f"Table: {schema_table}\n  Columns: {col_list}")

    return "\n\n".join(schema_parts)
