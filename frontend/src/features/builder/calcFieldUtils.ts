import type { CalculatedField, FilterOp, SemanticFieldMeta } from "../../types/spec";

// Separators that end a field-ref token in a formula (spaces, arithmetic, grouping).
const FORMULA_TOKEN_SEP = /[\s+\-*/()×÷,]/;

const OPS: { v: FilterOp; label: string }[] = [
  { v: "lt", label: "less than" },
  { v: "lte", label: "at most" },
  { v: "gt", label: "greater than" },
  { v: "gte", label: "at least" },
  { v: "eq", label: "is" },
  { v: "neq", label: "is not" },
  { v: "between", label: "is between" },
  { v: "contains", label: "contains" },
];

export const opLabel = (op: FilterOp) => OPS.find((o) => o.v === op)?.label ?? op;

export function formatCalcSummary(
  calc: CalculatedField,
  refLabel?: (ref: string) => string,
): string {
  if (calc.expression) return `Formula: ${calc.expression}`;
  const labelOf = (ref: string) => refLabel?.(ref) ?? ref.split(".").pop() ?? ref;
  const baseRef = calc.cases?.[0]?.ref ?? "";
  const field = baseRef ? labelOf(baseRef) : "value";
  const parts = (calc.cases ?? []).map(
    (c) => `${field} ${opLabel(c.op)} ${String(c.value)} → “${c.label}”`,
  );
  if (calc.else_label) parts.push(`otherwise → “${calc.else_label}”`);
  return parts.join(" · ") || "Custom column";
}

/** The identifier under the caret — the partial `payroll.gr` the user is typing. */
export function formulaTokenAt(
  expression: string,
  caret: number,
): { start: number; end: number; text: string } {
  const pos = Math.max(0, Math.min(caret, expression.length));
  let start = 0;
  for (let i = pos - 1; i >= 0; i--) {
    if (FORMULA_TOKEN_SEP.test(expression[i])) {
      start = i + 1;
      break;
    }
  }
  let end = expression.length;
  for (let i = pos; i < expression.length; i++) {
    if (FORMULA_TOKEN_SEP.test(expression[i])) {
      end = i;
      break;
    }
  }
  return { start, end, text: expression.slice(start, end) };
}

/** Replace the token under the caret with a field ref (e.g. `bas` → `payroll.basic`). */
export function insertFormulaRef(
  expression: string,
  caret: number,
  ref: string,
): { next: string; caret: number } {
  const tok = formulaTokenAt(expression, caret);
  const next = expression.slice(0, tok.start) + ref + expression.slice(tok.end);
  return { next, caret: tok.start + ref.length };
}

/** Match a typed query against a field's label, ref, or entity. */
export function matchFormulaFields(
  fields: SemanticFieldMeta[],
  query: string,
): SemanticFieldMeta[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  return fields.filter(
    (f) =>
      f.label.toLowerCase().includes(q) ||
      f.ref.toLowerCase().includes(q) ||
      f.entity.toLowerCase().includes(q),
  );
}
