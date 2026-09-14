"""Quick failure breakdown for all_66_executed.json."""
import json
import sys
from collections import Counter
from pathlib import Path

path = Path(__file__).parent / "question_bank_reports" / "all_66_executed.json"
d = json.loads(path.read_text(encoding="utf-8"))
fails = [r for r in d["results"] if not r.get("ok")]
print(f"failed {len(fails)} / 66")
no_sql = [r for r in fails if not r.get("sql")]
print(f"no_sql {len(no_sql)}:", [r["index"] + 1 for r in no_sql])
exec_err: Counter = Counter()
for r in fails:
    for e in r.get("errors") or []:
        key = e.split("\n")[0][:140]
        exec_err[key] += 1
print("--- errors ---")
for k, v in exec_err.most_common(20):
    print(v, k)
print("--- failed rows ---")
for r in fails:
    print(
        r["index"] + 1,
        r["section"][:20],
        "sql=" + ("Y" if r.get("sql") else "N"),
        r.get("sql_source") or "-",
        (r.get("errors") or [""])[0][:90],
    )
