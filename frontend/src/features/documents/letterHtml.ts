// Paste hygiene only — not a mapping layer.
// Word often pastes merge fields / tokens in a near-white colour. Drop those
// colours so body text applies. Field binding stays on the catalogue matcher.

const STYLE_ATTR = /(\sstyle\s*=\s*)(['"])(.*?)\2/gi;
const DECL = /([-\w]+)\s*:\s*([^;]+)/g;
const HEX = /^#([0-9a-f]{3,8})$/;
const RGB = /^rgba?\(\s*([0-9.]+%?)\s*,\s*([0-9.]+%?)\s*,\s*([0-9.]+%?)(?:\s*,\s*([0-9.]+))?\s*\)$/;
const COLOR_PROPS = new Set(["color", "mso-style-textfill-fill-color"]);
const MIN_CONTRAST = 3.0;

const NAMED: Record<string, [number, number, number, number]> = {
  white: [255, 255, 255, 1],
  silver: [192, 192, 192, 1],
  lightgray: [211, 211, 211, 1],
  lightgrey: [211, 211, 211, 1],
  gainsboro: [220, 220, 220, 1],
  whitesmoke: [245, 245, 245, 1],
  snow: [255, 250, 250, 1],
  ivory: [255, 255, 240, 1],
  azure: [240, 255, 255, 1],
  aliceblue: [240, 248, 255, 1],
  ghostwhite: [248, 248, 255, 1],
  floralwhite: [255, 250, 240, 1],
  seashell: [255, 245, 238, 1],
  beige: [245, 245, 220, 1],
  linen: [250, 240, 230, 1],
  oldlace: [253, 245, 230, 1],
  mintcream: [245, 255, 250, 1],
  honeydew: [240, 255, 240, 1],
  lavenderblush: [255, 240, 245, 1],
  lightcyan: [224, 255, 255, 1],
  darkgray: [169, 169, 169, 1],
  darkgrey: [169, 169, 169, 1],
};

function srgb(c: number): number {
  const x = c / 255;
  return x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4;
}

function luminance(r: number, g: number, b: number): number {
  return 0.2126 * srgb(r) + 0.7152 * srgb(g) + 0.0722 * srgb(b);
}

function contrastVsWhite(r: number, g: number, b: number): number {
  return 1.05 / (luminance(r, g, b) + 0.05);
}

function channel(raw: string): number | null {
  const s = raw.trim();
  const n = s.endsWith("%") ? Number(s.slice(0, -1)) * 2.55 : Number(s);
  return Number.isFinite(n) ? Math.max(0, Math.min(255, n)) : null;
}

function parseColor(raw: string): [number, number, number, number] | null {
  const s = raw.trim().toLowerCase();
  if (NAMED[s]) return NAMED[s];
  const hx = HEX.exec(s);
  if (hx) {
    const h = hx[1];
    const pair = (i: number) => parseInt(h.slice(i, i + 2), 16);
    if (h.length === 3) {
      return [parseInt(h[0] + h[0], 16), parseInt(h[1] + h[1], 16), parseInt(h[2] + h[2], 16), 1];
    }
    if (h.length === 4) {
      return [parseInt(h[0] + h[0], 16), parseInt(h[1] + h[1], 16), parseInt(h[2] + h[2], 16), parseInt(h[3] + h[3], 16) / 255];
    }
    if (h.length === 6) return [pair(0), pair(2), pair(4), 1];
    if (h.length === 8) return [pair(0), pair(2), pair(4), pair(6) / 255];
  }
  const rgb = RGB.exec(s);
  if (rgb) {
    const r = channel(rgb[1]); const g = channel(rgb[2]); const b = channel(rgb[3]);
    if (r == null || g == null || b == null) return null;
    const a = rgb[4] != null ? Number(rgb[4]) : 1;
    return [r, g, b, Number.isFinite(a) ? a : 1];
  }
  return null;
}

export function isFaintColor(raw: string): boolean {
  const c = parseColor(raw);
  if (!c) return false;
  const [r, g, b, a] = c;
  if (a < 0.45) return true;
  return contrastVsWhite(r, g, b) < MIN_CONTRAST;
}

function rewriteStyle(style: string): string {
  const kept: string[] = [];
  for (const m of style.matchAll(DECL)) {
    const prop = m[1].trim();
    const val = m[2].trim();
    const low = prop.toLowerCase();
    if (COLOR_PROPS.has(low) && isFaintColor(val)) continue;
    if (low === "opacity" && Number(val) < 0.45) continue;
    kept.push(`${prop}:${val}`);
  }
  return kept.join(";");
}

export function sanitizeLetterHtml(html: string | null | undefined): string {
  if (!html) return "";
  return html.replace(STYLE_ATTR, (_full, prefix: string, q: string, style: string) => {
    const cleaned = rewriteStyle(style);
    return cleaned.trim() ? `${prefix}${q}${cleaned}${q}` : "";
  });
}

/** Decode « » entities only. Wrappers (<< >>, « ») are detected separately. */
export function normalizeWordMergeHtml(html: string | null | undefined): string {
  if (!html) return "";
  return html
    .replace(/&laquo;|&#171;|&#x0*ab;/gi, "«")
    .replace(/&raquo;|&#187;|&#x0*bb;/gi, "»");
}

// The ASCII wrapper also matches the HTML-escaped form (&lt;&lt;...&gt;&gt;):
// a rich-text editor always entity-escapes literal < / > in text nodes, so a
// marker typed or pasted through the normal editor flow is stored escaped —
// keep the backend's identical wrapper regex (document_sample.py) in sync.
const MARK_RE = /«[^»]+»|(?:<<|&lt;&lt;)\s*[^>&]+?\s*(?:>>|&gt;&gt;)|\[\s*[A-Za-z][A-Za-z0-9_ ]*\s*\]/g;

export function preparePastedLetterHtml(html: string | null | undefined): string {
  return sanitizeLetterHtml(normalizeWordMergeHtml(html));
}

export function wordMarksKey(html: string | null | undefined): string {
  const decoded = normalizeWordMergeHtml(html);
  return [...decoded.matchAll(MARK_RE)].map((m) => m[0]).sort().join("|");
}

export function sanitizeDesignHtml<T extends {
  header_html?: string | null;
  footer_html?: string | null;
  blocks: { html?: string | null }[];
}>(design: T): T {
  return {
    ...design,
    header_html: design.header_html ? sanitizeLetterHtml(design.header_html) : design.header_html,
    footer_html: design.footer_html ? sanitizeLetterHtml(design.footer_html) : design.footer_html,
    blocks: design.blocks.map((b) => (b.html ? { ...b, html: sanitizeLetterHtml(b.html) } : b)),
  };
}
