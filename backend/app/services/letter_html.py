"""Normalise letter HTML pasted from Word (and similar).

Word mail-merge fields («HRIS», «Title», …) and leftover {{tokens}} often arrive
with a near-white / very-light grey colour — readable in Word's field shading,
invisible on a white letter. We drop those colours so body text colour applies.
"""

from __future__ import annotations

import re

_STYLE_ATTR = re.compile(r"""(\sstyle\s*=\s*)(['"])(.*?)\2""", re.I | re.DOTALL)
_DECL = re.compile(r"([-\w]+)\s*:\s*([^;]+)")
_HEX = re.compile(r"^#([0-9a-f]{3,8})$")
_RGB = re.compile(
    r"^rgba?\(\s*([0-9.]+%?)\s*,\s*([0-9.]+%?)\s*,\s*([0-9.]+%?)"
    r"(?:\s*,\s*([0-9.]+))?\s*\)$"
)
_COLOR_PROPS = {"color", "mso-style-textfill-fill-color"}

# Common Word / CSS names that are too light on a white page.
_NAMED = {
    "white": (255, 255, 255, 1.0),
    "silver": (192, 192, 192, 1.0),
    "lightgray": (211, 211, 211, 1.0),
    "lightgrey": (211, 211, 211, 1.0),
    "gainsboro": (220, 220, 220, 1.0),
    "whitesmoke": (245, 245, 245, 1.0),
    "snow": (255, 250, 250, 1.0),
    "ivory": (255, 255, 240, 1.0),
    "azure": (240, 255, 255, 1.0),
    "aliceblue": (240, 248, 255, 1.0),
    "ghostwhite": (248, 248, 255, 1.0),
    "floralwhite": (255, 250, 240, 1.0),
    "seashell": (255, 245, 238, 1.0),
    "beige": (245, 245, 220, 1.0),
    "linen": (250, 240, 230, 1.0),
    "oldlace": (253, 245, 230, 1.0),
    "mintcream": (245, 255, 250, 1.0),
    "honeydew": (240, 255, 240, 1.0),
    "lavenderblush": (255, 240, 245, 1.0),
    "lightcyan": (224, 255, 255, 1.0),
    "darkgray": (169, 169, 169, 1.0),
    "darkgrey": (169, 169, 169, 1.0),
    "lightslategray": (119, 136, 153, 1.0),
    "lightslategrey": (119, 136, 153, 1.0),
}

# Contrast vs white below this is treated as unreadable on the letter page.
_MIN_CONTRAST = 3.0


def _srgb(c: float) -> float:
    x = c / 255.0
    return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4


def _luminance(r: float, g: float, b: float) -> float:
    return 0.2126 * _srgb(r) + 0.7152 * _srgb(g) + 0.0722 * _srgb(b)


def _contrast_vs_white(r: float, g: float, b: float) -> float:
    return 1.05 / (_luminance(r, g, b) + 0.05)


def _channel(raw: str) -> float | None:
    s = raw.strip()
    try:
        if s.endswith("%"):
            return max(0.0, min(255.0, float(s[:-1]) * 2.55))
        return max(0.0, min(255.0, float(s)))
    except ValueError:
        return None


def _parse_color(raw: str) -> tuple[float, float, float, float] | None:
    s = raw.strip().lower()
    if s in _NAMED:
        return _NAMED[s]
    hx = _HEX.match(s)
    if hx:
        h = hx.group(1)
        if len(h) == 3:
            r, g, b = (int(c * 2, 16) for c in h)
            return (r, g, b, 1.0)
        if len(h) == 4:
            r, g, b, a = (int(c * 2, 16) for c in h)
            return (r, g, b, a / 255.0)
        if len(h) == 6:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
        if len(h) == 8:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16) / 255.0)
        return None
    rgb = _RGB.match(s)
    if rgb:
        r, g, b = (_channel(rgb.group(i)) for i in (1, 2, 3))
        if r is None or g is None or b is None:
            return None
        a = 1.0
        if rgb.group(4) is not None:
            try:
                a = float(rgb.group(4))
            except ValueError:
                a = 1.0
        return (r, g, b, a)
    return None


def is_faint_color(raw: str) -> bool:
    """True when the colour would be nearly invisible on a white letter."""
    parsed = _parse_color(raw)
    if not parsed:
        return False
    r, g, b, a = parsed
    if a < 0.45:
        return True
    return _contrast_vs_white(r, g, b) < _MIN_CONTRAST


def _rewrite_style(style: str) -> str:
    kept: list[str] = []
    for m in _DECL.finditer(style):
        prop, val = m.group(1).strip(), m.group(2).strip()
        low = prop.lower()
        if low in _COLOR_PROPS and is_faint_color(val):
            continue
        if low == "opacity":
            try:
                if float(val) < 0.45:
                    continue
            except ValueError:
                pass
        kept.append(f"{prop}:{val}")
    return ";".join(kept)


def sanitize_letter_html(html: str | None) -> str:
    """Drop near-invisible text colours; leave everything else (incl. tokens) intact."""
    if not html:
        return ""

    def repl(m: re.Match[str]) -> str:
        prefix, q, style = m.group(1), m.group(2), m.group(3)
        cleaned = _rewrite_style(style)
        if not cleaned.strip():
            return ""
        return f"{prefix}{q}{cleaned}{q}"

    return _STYLE_ATTR.sub(repl, html)
