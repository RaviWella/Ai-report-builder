"""
Restructure frontend datamart folders (move only — updates import paths).

Run from frontend/:  python ../backend/tools/restructure_datamart_frontend.py
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

FE = Path(__file__).resolve().parents[2] / "frontend" / "src"
DM = FE / "pages" / "datamart"

MOVES: dict[str, str] = {
    "chartAxisUtils.ts": "charts",
    "chartConfig.ts": "charts",
    "chartSuggestions.ts": "charts",
    "chartTypeAlternatives.ts": "charts",
    "GenerateChartModal.tsx": "charts",
    "DatamartCharts.tsx": "charts",
    "DatamartChartAxisControls.tsx": "charts",
    "DatamartChartSuggestions.tsx": "charts",
    "DatamartChartTypeSwitcher.tsx": "charts",
    "DatamartTable.tsx": "tables",
    "DatamartTableHeaderRow.tsx": "tables",
    "DatamartVirtualTableBody.tsx": "tables",
    "DatamartMessage.tsx": "components",
    "DatamartResultPanel.tsx": "components",
    "DatamartExtraBlockCard.tsx": "components",
    "DatamartPostProcessSummaries.tsx": "components",
    "DatamartGroupedResultMetrics.tsx": "components",
    "DatamartSyncProgress.tsx": "components",
    "DatamartSidebar.tsx": "components",
    "DatamartChatHeader.tsx": "components",
    "postProcessSummary.ts": "components",
    "datamartResultSplit.ts": "components",
}

IMPORT_RE = re.compile(
    r"""(from\s+['"])(\.(?:\./)*)(chartAxisUtils|chartConfig|chartSuggestions|"""
    r"""chartTypeAlternatives|GenerateChartModal|DatamartCharts|DatamartChartAxisControls|"""
    r"""DatamartChartSuggestions|DatamartChartTypeSwitcher|DatamartTable|"""
    r"""DatamartTableHeaderRow|DatamartVirtualTableBody|DatamartMessage|"""
    r"""DatamartResultPanel|DatamartExtraBlockCard|DatamartPostProcessSummaries|"""
    r"""DatamartGroupedResultMetrics|DatamartSyncProgress|DatamartSidebar|"""
    r"""DatamartChatHeader|postProcessSummary|datamartResultSplit)(['"])"""
)


def move_files() -> None:
    for name, folder in MOVES.items():
        src = DM / name
        if not src.exists():
            continue
        dest_dir = DM / folder
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / name
        if not dest.exists():
            shutil.move(str(src), str(dest))


def fix_imports() -> None:
    module_to_folder = {k.replace(".ts", "").replace(".tsx", ""): v for k, v in MOVES.items()}
    # Also map without extension for regex groups
    names = "|".join(re.escape(k.replace(".ts", "").replace(".tsx", "")) for k in MOVES)

    pattern = re.compile(
        rf"(from\s+['\"])(\.(?:\./)*)({names})(['\"])"
    )

    for tsf in FE.rglob("*"):
        if tsf.suffix not in (".ts", ".tsx"):
            continue
        if "node_modules" in tsf.parts:
            continue
        text = tsf.read_text(encoding="utf-8")
        original = text

        def repl(m: re.Match) -> str:
            prefix, dots, mod, quote = m.group(1), m.group(2), m.group(3), m.group(4)
            folder = module_to_folder.get(mod)
            if not folder:
                return m.group(0)
            # If importer is inside the same folder, keep relative
            try:
                rel = tsf.parent.relative_to(DM)
            except ValueError:
                rel = Path()
            if tuple(rel.parts) == (folder,):
                return m.group(0)
            # Build path from importer to datamart/{folder}/{mod}
            depth = len(rel.parts)
            up = "../" * depth if depth else "./"
            new_path = f"{up}{folder}/{mod}"
            return f"{prefix}{new_path}{quote}"

        text = pattern.sub(repl, text)

        if text != original:
            tsf.write_text(text, encoding="utf-8")


def write_readmes() -> None:
    for folder, desc in {
        "charts": "Chart rendering, configuration, and generation modal.",
        "tables": "Result tables and virtual scrolling.",
        "components": "Shared datamart UI building blocks.",
    }.items():
        d = DM / folder
        d.mkdir(parents=True, exist_ok=True)
        (d / "README.md").write_text(f"# datamart/{folder}\n\n{desc}\n", encoding="utf-8")

    readme = DM / "README.md"
    readme.write_text(
        """# Datamart UI

| Path | Purpose |
|------|---------|
| `DatamartWorkspace.tsx` | Route shell (chat vs template) |
| `DatamartChat.tsx` | Agent chat page |
| `DatamartTemplatePage.tsx` | Template viewer/editor |
| `chat/` | Composer, turns, follow-up mode |
| `components/` | Shared message/result/sidebar UI |
| `charts/` | Chart components and utilities |
| `tables/` | Table components |
| `report/` | Report canvas, export, validation |
| `templates/` | Template modification flow |
| `workspace/` | Workspace shell and sidebar contract |
| `hooks/` | React hooks |
| `lib/` | Pure helpers and API merge logic |
""",
        encoding="utf-8",
    )


def main() -> None:
    move_files()
    fix_imports()
    write_readmes()
    print("Frontend datamart restructure complete.")


if __name__ == "__main__":
    main()
