"""Human-readable explanation of a RuleReportSpec, for a non-technical (HR) reader.

Each governed expression is PARSED with Python's `ast` (the same family of nodes the
rule engine whitelists) and rendered to English by walking the tree — so the wording is
accurate and dynamic for ANY spec, not string-matched to one report. `inflect` gives
natural lists ("First Half or Second Half") and pluralisation.

Nothing here executes the expression; it only describes it.
"""
from __future__ import annotations

import ast
import re

import inflect

from app.domain.rule_report import RuleReportSpec

_p = inflect.engine()

_CMP = {
    ast.Eq: "is", ast.NotEq: "is not",
    ast.Gt: "is more than", ast.GtE: "is at least",
    ast.Lt: "is less than", ast.LtE: "is at most",
}
_BIN = {ast.Add: "plus", ast.Sub: "minus", ast.Mult: "times", ast.Div: "divided by"}
_AGG = {"sum": "the total of", "avg": "the average of", "count": "the count of",
        "min": "the lowest", "max": "the highest"}


def _num(v: object) -> str:
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


class _Renderer:
    """Walks an expression AST and returns plain English."""

    def __init__(self, consts: dict, defines: dict[str, str], labels: dict[str, str]):
        self.consts = consts or {}
        self.defines = defines or {}
        self.labels = labels or {}

    def word(self, name: str) -> str:
        if name in self.labels:
            return self.labels[name]
        return name.replace("_", " ")

    def render(self, expr: str) -> str:
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError:
            return expr
        return self._node(tree.body)

    # wrap compound sub-expressions so grouping is not lost
    def _sub(self, n: ast.AST) -> str:
        out = self._node(n)
        if isinstance(n, (ast.BinOp, ast.BoolOp, ast.Compare)):
            return f"({out})"
        return out

    def _node(self, n: ast.AST) -> str:  # noqa: PLR0911, C901
        if isinstance(n, ast.Constant):
            if isinstance(n.value, str):
                # prettify internal snake_case codes (e.g. public_holiday -> public holiday)
                txt = n.value.replace("_", " ") if re.fullmatch(r"[a-z][a-z0-9_]*", n.value) else n.value
                return f"“{txt}”"
            return _num(n.value)
        if isinstance(n, ast.Name):
            if n.id in ("row_value", "day_value"):         # the engine's per-row value keyword
                return "the row value"
            if n.id in self.consts:
                return _num(self.consts[n.id])
            if n.id in self.defines:                       # inline the shorthand's meaning
                return self.render(self.defines[n.id])
            return self.word(n.id)
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN:
            return f"{self._sub(n.left)} {_BIN[type(n.op)]} {self._sub(n.right)}"
        if isinstance(n, ast.UnaryOp):
            if isinstance(n.op, ast.Not):
                return f"not {self._sub(n.operand)}"
            if isinstance(n.op, ast.USub):
                return f"minus {self._sub(n.operand)}"
            return self._node(n.operand)
        if isinstance(n, ast.BoolOp):
            joiner = " and " if isinstance(n.op, ast.And) else " or "
            return joiner.join(self._sub(v) for v in n.values)
        if isinstance(n, ast.Compare) and n.ops:
            op = n.ops[0]
            left = self._node(n.left)
            target = n.comparators[0]
            if isinstance(op, (ast.In, ast.NotIn)):
                elts = target.elts if isinstance(target, (ast.Tuple, ast.List)) else [target]
                items = [self._node(e) for e in elts]
                verb = "is one of" if isinstance(op, ast.In) else "is none of"
                return f"{left} {verb} {_p.join(items, conj='or')}"
            return f"{left} {_CMP.get(type(op), '?')} {self._node(target)}"
        if isinstance(n, ast.Call):
            fn = getattr(n.func, "id", "")
            args = [self._node(a) for a in n.args]
            if fn == "coalesce":                           # missing value treated as 0
                return args[0] if args else ""
            if fn in ("max", "greatest"):
                return f"whichever is larger of {_p.join(args)}"
            if fn in ("min", "least"):
                return f"whichever is smaller of {_p.join(args)}"
            if fn == "abs":
                return f"the size of {args[0]}"
            if fn == "round":
                return f"{args[0]} rounded"
            return f"{fn} of {_p.join(args)}"
        try:
            return ast.unparse(n)
        except Exception:  # noqa: BLE001
            return "…"


def explain_spec(spec: RuleReportSpec, labels: dict[str, str] | None = None) -> dict:
    """Return {"sections": [{"title", "lines"}]} — a readable paraphrase of the spec."""
    labels = labels or {}
    r = _Renderer(spec.constants, spec.day_value.define, labels)

    def lab(name: str) -> str:
        return labels.get(name) or name.replace("_", " ")

    sections: list[dict] = []

    # where the data comes from
    if spec.sources:
        srcs = [s.table for s in spec.sources.values()]
    elif spec.source:
        srcs = [spec.source]
    else:
        srcs = []
    if srcs:
        def _src_name(table: str) -> str:
            if "<" in table:                      # a placeholder — show it verbatim
                return table
            base = table.split(".")[-1]
            return re.sub(r"^(mart_|fct_|dim_)", "", base).replace("_", " ")
        sections.append({"title": "Where the numbers come from",
                         "lines": [f"The {_src_name(s)} table" + ("" if "<" in s else f" ({s})")
                                   for s in srcs]})

    # per-row value (domain-neutral: not every report is about days or hours)
    row_lines = []
    for case in spec.day_value.cases:
        row_lines.append(f"If {r.render(case.when)}, the value is {r.render(case.value)}.")
    if spec.day_value.else_value:
        row_lines.append(f"Otherwise, the value is {r.render(spec.day_value.else_value)}.")
    if row_lines:
        sections.append({"title": "For each row, work out its value", "lines": row_lines})

    # roll-ups, grouped by the grain (whatever it is — employee per period, etc.)
    grain_words = _p.join([lab(g) for g in spec.grain]) if spec.grain else "group"
    roll_lines = []
    for name, rule in spec.rollup.items():
        expr_part, _, where = rule.partition(" where ")
        m = re.match(r"^\s*(\w+)\((.+)\)\s*$", expr_part.strip())
        if m and m.group(1).lower() in _AGG:
            phrase = f"{_AGG[m.group(1).lower()]} {r.render(m.group(2))}"
        else:
            phrase = r.render(expr_part)
        if where.strip():
            phrase += f", counting only rows where {r.render(where)}"
        roll_lines.append(f"{lab(name)} = {phrase}.")
    if roll_lines:
        sections.append({"title": f"For each {grain_words}, add up", "lines": roll_lines})

    # final formulas
    comp_lines = [f"{lab(name)} = {r.render(expr)}." for name, expr in spec.compute.items()]
    if comp_lines:
        sections.append({"title": "Then calculate", "lines": comp_lines})

    # runtime filters
    filt = [f"{f.label or f.name} — {r.word(f.column) if f.column else 'a value'}"
            for f in spec.filters]
    if filt:
        sections.append({"title": "Before running, the user chooses", "lines": filt})

    return {"sections": sections}
