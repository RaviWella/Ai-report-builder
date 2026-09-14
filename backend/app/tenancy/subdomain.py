"""Normalize subdomain values received from clients."""


def normalize_subdomain(raw: str) -> str:
    """Fold HRIS host labels to identifier-safe form (coca-cola → coca_cola).

    Used for PG schema names, warehouse datamart keys (mint_{key}), and
    provision-row lookup when JWT tenant_id still has hyphens or dots.
    """
    return raw.replace("-", "_").replace(".", "_").lower().strip()
