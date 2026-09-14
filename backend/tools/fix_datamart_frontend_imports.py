"""Fix relative imports inside moved frontend datamart subfolders."""
from pathlib import Path

FE = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages" / "datamart"

SUB = ("charts", "tables", "components")

for folder in SUB:
    d = FE / folder
    if not d.is_dir():
        continue
    for tsf in d.rglob("*"):
        if tsf.suffix not in (".ts", ".tsx"):
            continue
        text = tsf.read_text(encoding="utf-8")
        original = text
        for sub in ("lib", "hooks", "report", "chat", "templates", "workspace"):
            text = text.replace(f"from './{sub}/", f"from '../{sub}/")
            text = text.replace(f'from "./{sub}/', f'from "../{sub}/')
        if folder == "components":
            text = text.replace("from './DatamartTable'", "from '../tables/DatamartTable'")
            text = text.replace('from "./DatamartTable"', 'from "../tables/DatamartTable"')
        if text != original:
            tsf.write_text(text, encoding="utf-8")
            print(f"fixed internal {tsf.relative_to(FE)}")

# Fix remaining external references to old root paths
replacements = [
    ("from '../DatamartMessage'", "from '../components/DatamartMessage'"),
    ('from "../DatamartMessage"', 'from "../components/DatamartMessage"'),
    ("from './DatamartMessage'", "from './components/DatamartMessage'"),
    ('from "./DatamartMessage"', 'from "./components/DatamartMessage"'),
    ("from '../DatamartSidebar'", "from '../components/DatamartSidebar'"),
    ('from "../DatamartSidebar"', 'from "../components/DatamartSidebar"'),
    ("from './DatamartSidebar'", "from './components/DatamartSidebar'"),
    ('from "./DatamartSidebar"', 'from "./components/DatamartSidebar"'),
    ("from '../GenerateChartModal'", "from '../charts/GenerateChartModal'"),
    ('from "../GenerateChartModal"', 'from "../charts/GenerateChartModal"'),
    ("from './GenerateChartModal'", "from './charts/GenerateChartModal'"),
    ('from "./GenerateChartModal"', 'from "./charts/GenerateChartModal"'),
    ("from '../DatamartCharts'", "from '../charts/DatamartCharts'"),
    ('from "../DatamartCharts"', 'from "../charts/DatamartCharts"'),
    ("from './DatamartCharts'", "from './charts/DatamartCharts'"),
    ("from '../DatamartSyncProgress'", "from '../components/DatamartSyncProgress'"),
    ("from './DatamartSyncProgress'", "from './components/DatamartSyncProgress'"),
    ("from '../DatamartChatHeader'", "from '../components/DatamartChatHeader'"),
    ("from './DatamartChatHeader'", "from './components/DatamartChatHeader'"),
    ("from '../DatamartResultPanel'", "from '../components/DatamartResultPanel'"),
    ("from './DatamartResultPanel'", "from './components/DatamartResultPanel'"),
    ("from '../DatamartExtraBlockCard'", "from '../components/DatamartExtraBlockCard'"),
    ("from './DatamartExtraBlockCard'", "from './components/DatamartExtraBlockCard'"),
    ("from '../DatamartTable'", "from '../tables/DatamartTable'"),
    ("from './DatamartTable'", "from './tables/DatamartTable'"),
]

for tsf in FE.rglob("*"):
    if tsf.suffix not in (".ts", ".tsx"):
        continue
    text = tsf.read_text(encoding="utf-8")
    original = text
    for old, new in replacements:
        text = text.replace(old, new)
    if text != original:
        tsf.write_text(text, encoding="utf-8")
        print(f"fixed external {tsf.relative_to(FE)}")

print("done")
