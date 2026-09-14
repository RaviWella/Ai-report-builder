// Visual order for the Excel mapping review: sheet columns stay in file order,
// and extra (manually added / custom) fields slot between them.
//
// `extraAfter[ref] === header` means the extra sits immediately after that
// sheet column. `null` means it sits before the first sheet column.

export type MappingDisplayRow =
  | { kind: "mapped"; header: string }
  | { kind: "extra"; ref: string };

export function buildMappingDisplayRows(
  mappingHeaders: string[],
  extraRefs: string[],
  extraAfter: Record<string, string | null>,
): MappingDisplayRow[] {
  const lastHeader = mappingHeaders[mappingHeaders.length - 1] ?? null;
  const buckets = new Map<string | null, string[]>();
  const push = (after: string | null, ref: string) => {
    const list = buckets.get(after) ?? [];
    list.push(ref);
    buckets.set(after, list);
  };

  for (const ref of extraRefs) {
    const after = Object.prototype.hasOwnProperty.call(extraAfter, ref)
      ? extraAfter[ref]
      : lastHeader;
    // Ignore a stale header that is no longer in the sheet.
    const valid =
      after === null || mappingHeaders.includes(after) ? after : lastHeader;
    push(valid, ref);
  }

  const rows: MappingDisplayRow[] = [];
  for (const ref of buckets.get(null) ?? []) {
    rows.push({ kind: "extra", ref });
  }
  for (const header of mappingHeaders) {
    rows.push({ kind: "mapped", header });
    for (const ref of buckets.get(header) ?? []) {
      rows.push({ kind: "extra", ref });
    }
  }
  return rows;
}

export function extraAfterFromRows(
  rows: MappingDisplayRow[],
): Record<string, string | null> {
  const out: Record<string, string | null> = {};
  let lastHeader: string | null = null;
  for (const row of rows) {
    if (row.kind === "mapped") lastHeader = row.header;
    else out[row.ref] = lastHeader;
  }
  return out;
}

export function moveExtraInRows(
  rows: MappingDisplayRow[],
  ref: string,
  dir: -1 | 1,
): MappingDisplayRow[] | null {
  const i = rows.findIndex((r) => r.kind === "extra" && r.ref === ref);
  const j = i + dir;
  if (i < 0 || j < 0 || j >= rows.length) return null;
  const next = rows.slice();
  [next[i], next[j]] = [next[j], next[i]];
  return next;
}

/** Report column order implied by the visual mapping list. */
export function reportOrderFromRows(
  rows: MappingDisplayRow[],
  choice: Record<string, string | null>,
  selectedRefs: Iterable<string>,
): string[] {
  const selected = selectedRefs instanceof Set ? selectedRefs : new Set(selectedRefs);
  const order: string[] = [];
  for (const row of rows) {
    if (row.kind === "extra") {
      if (selected.has(row.ref)) order.push(row.ref);
      continue;
    }
    const ref = choice[row.header];
    if (ref && selected.has(ref)) order.push(ref);
  }
  return order;
}
