"""Configure process-wide logging for local uvicorn (INFO app + datamart)."""
from __future__ import annotations

import logging
import sys


def configure_logging(*, debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return

    logging.basicConfig(
        level=level,
        format="%(levelname)s [%(name)s] %(message)s",
        stream=sys.stdout,
        force=True,
    )
    # SQLAlchemy SQL echo is noisy during startup
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("alembic").setLevel(logging.INFO)
    logging.getLogger("ai_services.datamart").setLevel(logging.DEBUG if debug else logging.INFO)
    logging.getLogger("app").setLevel(logging.DEBUG if debug else logging.INFO)
