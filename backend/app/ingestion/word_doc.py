"""Read a legacy Word .doc (OLE2) as plain lines — same privacy rules as .docx.

python-docx only understands OOXML (.docx). Older .doc files are OLE2 compound
documents; if we send them to the Excel parser, xlrd raises
"Can't find workbook in OLE2 compound document". This module pulls the
WordDocument stream via xlrd's already-bundled OLE reader and reconstructs
text from the piece table ([MS-DOC] 2.4.1).
"""
from __future__ import annotations

import re
import struct

_OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_WORD_IDENT = 0xA5EC
_MERGEFIELD = re.compile(r"MERGEFIELD\s+\"?([A-Za-z0-9_]+)\"?", re.I)
_RTF_HEX = re.compile(r"\\'([0-9a-fA-F]{2})")
_RTF_CTRL = re.compile(r"\\[a-zA-Z]+\d* ?")


def looks_like_ole2(content: bytes) -> bool:
    return content.startswith(_OLE2_MAGIC)


def is_legacy_word(filename: str = "", content_type: str = "", content: bytes | None = None) -> bool:
    """True for Word 97-2003 .doc/.dot (not .docx).

    Content is authoritative whenever we have it: a genuine .xls/.ppt (also an
    OLE2 container, just with a different stream inside) or a .docx renamed to
    .doc must not be misrouted here just because of a claimed extension."""
    name = (filename or "").lower()
    ct = (content_type or "").lower()
    if name.endswith((".docx", ".dotx")):
        return False
    if content is not None:
        return looks_like_ole2(content) and _ole_has_word_stream(content)
    if name.endswith((".doc", ".dot")):
        return True
    return ct in {"application/msword", "application/x-msword", "application/doc"}


def extract_doc_lines(content: bytes) -> list[str]:
    """Visible paragraph/table lines from a .doc (or RTF saved as .doc)."""
    if content.lstrip().startswith(b"{\\rtf"):
        return _lines_from_text(_rtf_text(content))
    try:
        text = _doc_text(content)
    except ValueError:
        raise  # a specific, actionable message (encrypted / truncated / not Word) — keep it
    except Exception as exc:
        raise ValueError(
            "Couldn’t read that Word file. Save it as .docx and try again."
        ) from exc
    lines = _lines_from_text(text)
    if not lines:
        raise ValueError("No text could be read from that Word file.")
    return lines


def _ole_has_word_stream(content: bytes) -> bool:
    try:
        from xlrd.compdoc import CompDoc

        return CompDoc(content).get_named_stream("WordDocument") is not None
    except Exception:
        return False


def _doc_streams(content: bytes) -> tuple[bytes, bytes]:
    from xlrd.compdoc import CompDoc, CompDocError

    if not looks_like_ole2(content):
        raise ValueError("Not a Word 97-2003 (.doc) file.")
    try:
        ole = CompDoc(content)
    except CompDocError as exc:
        raise ValueError("Couldn’t open that Word file.") from exc
    doc = ole.get_named_stream("WordDocument")
    if not doc:
        raise ValueError("Not a Word document.")
    if len(doc) < 0x1C:
        raise ValueError("Word file header is truncated.")
    ident = struct.unpack_from("<H", doc, 0)[0]
    if ident != _WORD_IDENT:
        raise ValueError("Not a Word document.")
    flags = struct.unpack_from("<H", doc, 0x0A)[0]
    if flags & 0x0100:
        raise ValueError("This Word file is encrypted. Save it as .docx and try again.")
    table_name = "1Table" if flags & 0x0200 else "0Table"
    table = ole.get_named_stream(table_name) or b""
    return doc, table


def _doc_text(content: bytes) -> str:
    doc, table = _doc_streams(content)
    fc_min = struct.unpack_from("<I", doc, 0x18)[0]
    fc_mac = struct.unpack_from("<I", doc, 0x1C)[0]
    ccp_text = struct.unpack_from("<I", doc, 0x4C)[0] if len(doc) >= 0x50 else 0
    fc_clx = struct.unpack_from("<I", doc, 0x1A2)[0] if len(doc) >= 0x1AA else 0
    lcb_clx = struct.unpack_from("<I", doc, 0x1A6)[0] if len(doc) >= 0x1AA else 0

    pieces = _parse_piece_table(table, fc_clx, lcb_clx) if lcb_clx else []
    if not pieces:
        pieces = [(fc_min, max(0, fc_mac - fc_min))]

    parts: list[str] = []
    for fc, ccp in pieces:
        if ccp <= 0:
            continue
        if fc & 0x40000000:
            off = (fc ^ 0x40000000) >> 1
            parts.append(doc[off : off + ccp].decode("cp1252", errors="replace"))
        else:
            parts.append(doc[fc : fc + ccp * 2].decode("utf-16-le", errors="replace"))
    text = "".join(parts)
    if ccp_text > 0:
        text = text[:ccp_text]
    return _clean_binary_text(text)


def _parse_piece_table(table: bytes, fc_clx: int, lcb_clx: int) -> list[tuple[int, int]]:
    clx = table[fc_clx : fc_clx + lcb_clx]
    i = 0
    while i < len(clx):
        clxt = clx[i]
        i += 1
        if clxt == 1:  # grpprl — skip
            if i + 2 > len(clx):
                break
            skip = struct.unpack_from("<H", clx, i)[0]
            i += 2 + skip
            continue
        if clxt != 2:  # not plcfpcd
            break
        if i + 4 > len(clx):
            break
        length = struct.unpack_from("<I", clx, i)[0]
        i += 4
        n = (length - 4) // 12
        if n <= 0 or i + 4 * (n + 1) + 8 * n > len(clx):
            break
        cps = [struct.unpack_from("<I", clx, i + 4 * k)[0] for k in range(n + 1)]
        i += 4 * (n + 1)
        return [
            (struct.unpack_from("<I", clx, i + 8 * k + 2)[0], cps[k + 1] - cps[k])
            for k in range(n)
        ]
    return []


def _field_to_mark(code: str, shown: str = "") -> str:
    m = _MERGEFIELD.search(code)
    if m:
        return f"«{m.group(1)}»"
    # No MERGEFIELD and no cached display result (e.g. a PAGE/REF/DATE field
    # whose result wasn't stored in this piece) — drop it rather than leaking
    # Word's internal field-instruction syntax into the visible text.
    return shown.strip()


def _resolve_fields(text: str) -> str:
    """Replace \\x13 code \\x14 result \\x15 (or \\x13 code \\x15) field runs with
    a single display value. Word allows NESTED fields (an IF wrapping a
    MERGEFIELD, say) — walked with an explicit stack rather than a flat regex,
    so an inner field resolves before the outer one's code/result is read."""
    out: list[str] = []
    stack: list[dict[str, list[str] | bool]] = []

    def dest() -> list[str]:
        if not stack:
            return out
        top = stack[-1]
        return top["result"] if top["in_result"] else top["code"]  # type: ignore[return-value]

    for ch in text:
        if ch == "\x13":
            stack.append({"code": [], "result": [], "in_result": False})
        elif ch == "\x14" and stack:
            stack[-1]["in_result"] = True
        elif ch == "\x15" and stack:
            field = stack.pop()
            dest().append(_field_to_mark("".join(field["code"]), "".join(field["result"])))
        else:
            dest().append(ch)
    # Unbalanced \x13 with no closing \x15 (corrupted/truncated doc) — flush
    # whatever was captured rather than losing it silently.
    while stack:
        field = stack.pop()
        dest().append(_field_to_mark("".join(field["code"]), "".join(field["result"])))
    return "".join(out)


def _clean_binary_text(text: str) -> str:
    text = _resolve_fields(text)
    text = text.replace("\x07\x07", "\n").replace("\x07", "\t")
    text = text.replace("\r", "\n").replace("\x0b", "\n").replace("\x0c", "\n")
    return re.sub(r"[\x00-\x08\x0e-\x1f]", "", text)


def _rtf_text(content: bytes) -> str:
    s = content.decode("latin-1", errors="replace")
    s = _RTF_HEX.sub(lambda m: chr(int(m.group(1), 16)), s)
    s = re.sub(r"\\par[d]?", "\n", s)
    s = _RTF_CTRL.sub("", s)
    return re.sub(r"[{}]", "", s)


def _lines_from_text(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]
