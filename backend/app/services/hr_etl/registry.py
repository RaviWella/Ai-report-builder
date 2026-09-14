"""Select ETL extractor set from application settings."""
from __future__ import annotations

from typing import Callable

from app.core.config import settings


def get_extractors(profile: str | None = None) -> tuple[list[tuple[str, Callable]], set[str]]:
    """Return (EXTRACTORS, INCREMENTAL_TABLES) for the given extractor profile."""
    prof = (profile or settings.MYSQL_EXTRACTOR_PROFILE or "generic").strip().lower()

    if prof == "minthrm":
        from app.services.hr_etl import extractors_minthrm as mod

        return mod.EXTRACTORS, mod.INCREMENTAL_TABLES

    from app.services.hr_etl import extractors as mod

    return mod.EXTRACTORS, mod.INCREMENTAL_TABLES
