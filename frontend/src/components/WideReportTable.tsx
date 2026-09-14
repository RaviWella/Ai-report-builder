/**
 * Horizontally scrollable report table.
 *
 * MUI Table always sets width:100% on the underlying <table>, which caps
 * scrollWidth to the viewport — wide reports cannot scroll to the last columns.
 * This uses a plain HTML table inside a dedicated overflow-x container.
 */
import { type ReactNode, useEffect, useRef, useState } from "react";
import { Box, Typography } from "@mui/material";

const TH_STYLE: React.CSSProperties = {
  whiteSpace: "nowrap",
  padding: "10px 14px",
  fontSize: "0.72rem",
  fontWeight: 600,
  color: "#374151",
  textAlign: "left",
  backgroundColor: "#F9FAFB",
  borderBottom: "1px solid #E5E7EB",
  verticalAlign: "middle",
  minWidth: 120,
};

const TD_STYLE: React.CSSProperties = {
  whiteSpace: "nowrap",
  padding: "10px 14px",
  fontSize: "0.8rem",
  color: "#1A1A1A",
  textAlign: "left",
  borderBottom: "1px solid #E5E7EB",
  verticalAlign: "middle",
  minWidth: 120,
};

export interface WideReportTableProps {
  columns: string[];
  rows: Record<string, unknown>[];
  colLabel?: (key: string) => string;
  cellText?: (value: unknown) => string;
  footer?: ReactNode;
  /** px — used only to hint minimum table width when cells are empty */
  colMinWidth?: number;
  /** When set, the scroll area also scrolls vertically (e.g. builder preview). */
  maxHeight?: number | string;
  /** Inside a parent card — no outer border/radius on the scroll box. */
  embedded?: boolean;
}

export function WideReportTable({
  columns,
  rows,
  colLabel = (c) => c,
  cellText = (v) => (v == null ? "" : String(v)),
  footer,
  colMinWidth = 120,
  maxHeight,
  embedded = false,
}: WideReportTableProps) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [scrollHint, setScrollHint] = useState(false);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    const update = () => {
      const wider = el.scrollWidth > el.clientWidth + 4;
      const atEnd = el.scrollLeft + el.clientWidth >= el.scrollWidth - 4;
      setScrollHint(wider && !atEnd);
    };

    update();
    el.addEventListener("scroll", update, { passive: true });
    const ro = new ResizeObserver(update);
    ro.observe(el);
    if (el.firstElementChild) ro.observe(el.firstElementChild);

    return () => {
      el.removeEventListener("scroll", update);
      ro.disconnect();
    };
  }, [columns, rows]);

  const minTableWidth = Math.max(columns.length * colMinWidth, 480);

  return (
    <Box sx={{ position: "relative", width: "100%", maxWidth: "100%", minWidth: 0 }}>
      {scrollHint && (
        <Typography
          variant="caption"
          sx={{ position: "absolute", right: 0, top: -20, color: "text.secondary", userSelect: "none" }}
        >
          Scroll horizontally for more columns →
        </Typography>
      )}
      <Box
        ref={scrollRef}
        sx={{
          width: "100%",
          maxWidth: "100%",
          minWidth: 0,
          overflowX: "auto",
          overflowY: maxHeight ? "auto" : "hidden",
          maxHeight,
          WebkitOverflowScrolling: "touch",
          overscrollBehaviorX: "contain",
          ...(embedded
            ? { border: "none", borderRadius: 0 }
            : {
              border: "1px solid",
              borderColor: "divider",
              borderRadius: footer ? "8px 8px 0 0" : 2,
            }),
          bgcolor: "background.paper",
        }}
      >
        <table
          className="wide-report-table"
          style={{
            width: "max-content",
            minWidth: minTableWidth,
            borderCollapse: "collapse",
            tableLayout: "auto",
            margin: 0,
          }}
        >
          <thead>
            <tr>
              {columns.map((c, i) => (
                <th key={`${i}:${c}`} scope="col" style={TH_STYLE}>
                  {colLabel(c)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <tr key={ri}>
                {columns.map((c, ci) => (
                  <td key={`${ci}:${c}`} style={TD_STYLE}>
                    {cellText(row[c])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </Box>
      {footer}
    </Box>
  );
}
