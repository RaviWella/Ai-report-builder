"""Fix config import paths broken by restructure_datamart_packages.py."""
from pathlib import Path

DM = Path(__file__).resolve().parents[1] / "app" / "services" / "ai_services" / "datamart"
SUBPKGS = (
    "sql",
    "llm",
    "prompts",
    "scenario",
    "semantic",
    "domain_sql",
    "validation",
    "postprocess",
    "workspace",
    "orchestration",
    "pipeline",
)

for pkg in SUBPKGS:
    d = DM / pkg
    if not d.is_dir():
        continue
    for pyf in d.rglob("*.py"):
        text = pyf.read_text(encoding="utf-8")
        original = text
        text = text.replace("from . import config as", "from .. import config as")
        text = text.replace("from ..config import settings", "from app.core.config import settings")
        if text != original:
            pyf.write_text(text, encoding="utf-8")
            print(f"fixed {pyf.relative_to(DM.parent.parent.parent)}")

print("done")
