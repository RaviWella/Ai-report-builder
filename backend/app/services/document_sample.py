"""Turn an uploaded SAMPLE letter (Word / PDF / image / Excel) into a canvas design.

DETERMINISTIC & FAST — no LLM call. We read the sample's text locally
(pdfplumber / Tesseract), detect the per-recipient DYNAMIC values with pattern
rules, and map each to a semantic field with the SAME local fuzzy matcher the
report Excel-mapping uses (field labels/refs + glossary aliases). Confident spans
become `{{ref}}` merge tokens; static boilerplate is left as text; detected-but-
unmatched spans are returned for a quick manual bind.

What we detect:
  1. "Label: value" lines            -> map the label, tokenise the value
  2. "Dear <name>," greeting          -> the name field
  3. "Mr/Ms <name>" recipient line    -> the name field
  4. amounts (Rs. / figures) in prose -> map the words just before them
Nothing is HR-specific; every mapping is a semantic ref resolved per tenant.
Only labels are mapped — the sample's values are never bound or stored.
"""

from __future__ import annotations

import re
import uuid
from html import escape, unescape
from typing import Callable

from app.core.tenancy import TenantContext
from app.domain.document_design import DesignBlock, DocumentDesign
from app.domain.enums import FieldType
from app.ingestion.document_parser import extract_lines, is_text_document, parse_document
from app.services.ai_service import AIService

_TAG = re.compile(r"<[^>]+>")
_EXISTING_TOKEN = re.compile(r"\{\{[^}]+\}\}")

Matcher = Callable[[str], "tuple[str | None, float]"]

_FIELD_LINE = re.compile(r"^(.{2,40}?)\s*[:：]\s*(\S.*)$")
_GREETING = re.compile(r"^(Dear|To)\s+(.+?)[,:]?\s*$", re.I)
_TITLE = re.compile(r"^(Mr|Mrs|Ms|Miss|Dr|Rev)\.?\s+([A-Z].*?)\s*$")
# Money / figures: Rs.45000.00, LKR 1,200, $50, or a bare grouped decimal 45,000.00
_AMOUNT = re.compile(r"(?:Rs\.?|LKR|USD|\$)\s*[\d,]+(?:\.\d+)?/?=?|\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b", re.I)
# Words that are never the field label (so the cue before an amount is clean).
_STOP = {
    "of", "the", "a", "an", "is", "has", "have", "been", "your", "you", "will", "and",
    "to", "rs", "lkr", "usd", "consolidated", "receive", "that", "with", "for", "by",
    "increased", "increase", "pleased", "inform", "total", "be", "on", "as", "at",
}
_MIN = 0.6  # accept a local field match at/above this (mirrors the resolver's floor)

# Merge *names* may be wrapped however the source wrote them — or not at all.
# We only extract the name; the catalogue matcher decides the ref.
# The ASCII wrapper also accepts the HTML-escaped form (&lt;&lt;...&gt;&gt;):
# a rich-text editor always entity-escapes literal < / > in text nodes, so a
# marker typed or pasted through the normal editor flow never appears as a
# literal "<<" in the stored html — only matching the escaped form too keeps
# the two ways of writing it equivalent for detection purposes.
_MARK_WRAPPED = re.compile(
    r"«([^»]+)»"                                      # Word: «Display_Name»
    r"|(?:<<|&lt;&lt;)\s*([^>&]+?)\s*(?:>>|&gt;&gt;)"  # ASCII: <<Display_Name>>
    r"|\[\s*([A-Za-z][A-Za-z0-9_ ]*)\s*\]"             # [Display_Name]
)
_MARK_CURLY = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
_MARK_BARE = re.compile(r"\b([A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+_?)\b")
# A ref, optionally with its value-map suffix (see document_design.parse_token) —
# recognizes an already-resolved {{ref|value=text|...}} so a re-run of the Word
# mapper never mistakes its own output for a new, unmatched cue.
_SEMANTIC_REF = re.compile(r"^[a-z][a-z0-9_]*\.[a-zA-Z0-9_.]+(?:\|[^|{}=]+=[^|{}]*)*$")


def _token(ref: str) -> str:
    return "{{" + ref + "}}"


def _word_cue(raw: str) -> str:
    return " ".join(_TAG.sub("", unescape(raw)).replace("_", " ").strip().split())


def _cues_to_try(cue: str) -> list[str]:
    """Full Word name first, then shorter tokens (Prsent_Designation_ → Designation)."""
    words = [w for w in cue.split() if w]
    out: list[str] = [cue]
    if len(words) >= 2:
        out.append(" ".join(words[-2:]))
        out.append(words[-1])
    for w in words:
        if len(re.sub(r"[^A-Za-z]", "", w)) >= 4 and w not in out:
            out.append(w)
    return out


def _best_word_match(cue: str, match: Matcher) -> tuple[str | None, float]:
    best_ref, best_score, best_len = None, 0.0, 0
    for c in _cues_to_try(cue):
        ref, score = match(c)
        if not ref or score < _MIN:
            continue
        if score > best_score or (score == best_score and len(c) > best_len):
            best_ref, best_score, best_len = ref, score, len(c)
    return best_ref, best_score


_LAQUO_RE = re.compile(r"&laquo;|&#171;|&#x0*ab;", re.I)
_RAQUO_RE = re.compile(r"&raquo;|&#187;|&#x0*bb;", re.I)


def _decode_chevrons(html: str) -> str:
    return _RAQUO_RE.sub("»", _LAQUO_RE.sub("«", html))


def _bind_cue(raw: str, match: Matcher) -> tuple[str | None, float, str]:
    cue = _word_cue(raw)
    if not cue:
        return None, 0.0, ""
    ref, score = _best_word_match(cue, match)
    return ref, score, cue


def map_word_merge_fields(
    html: str | None, match: Matcher, *, include_bare: bool = True
) -> tuple[str, list[str], list[str]]:
    """Bind merge *names* — «Name», <<Name>>, [Name], {{Name}}, or Name_with_underscores —
    through the catalogue matcher. Wrappers are not hardcoded to fields.

    `include_bare=False` skips the Name_with_underscores pass — for a letter
    that isn't known to have come from a Word template, that pattern also
    matches ordinary prose (an email address, a reference code) and would
    silently swallow it into a merge token."""
    if not html:
        return "", [], []
    html = _decode_chevrons(html)
    mapped: list[str] = []
    unmatched: list[str] = []

    def apply_match(raw: str, original: str) -> str:
        if _SEMANTIC_REF.match(raw.strip()):
            return original
        ref, score, cue = _bind_cue(raw, match)
        if not cue:
            return original
        if ref and score >= _MIN:
            if ref not in mapped:
                mapped.append(ref)
            return _token(ref)
        if cue not in unmatched:
            unmatched.append(cue)
        return original

    def wrapped(m: re.Match[str]) -> str:
        raw = next((g for g in m.groups() if g), "")
        return apply_match(raw, m.group(0))

    html = _MARK_WRAPPED.sub(wrapped, html)

    def curly(m: re.Match[str]) -> str:
        return apply_match(m.group(1), m.group(0))

    html = _MARK_CURLY.sub(curly, html)

    def bare(m: re.Match[str]) -> str:
        name = m.group(1)
        i, j = m.start(), m.end()
        left, right = html[max(0, i - 2):i], html[j:j + 2]
        if left.endswith(("«", "[", "{")) or right.startswith(("»", "]", "}")):
            return name
        if left.endswith("<<") or right.startswith(">>"):
            return name
        return apply_match(name, name)

    if include_bare:
        html = _MARK_BARE.sub(bare, html)
    return html, mapped, unmatched


def apply_word_fields_to_design(
    design: DocumentDesign, match: Matcher, *, include_bare: bool = True
) -> tuple[list[str], list[str]]:
    """Map «Field» markers in every text block + letterhead. Mutates `design`."""
    mapped: list[str] = []
    unmatched: list[str] = []

    def apply(html: str | None) -> str | None:
        if not html:
            return html
        out, refs, un = map_word_merge_fields(html, match, include_bare=include_bare)
        for r in refs:
            if r not in mapped:
                mapped.append(r)
        for u in un:
            if u not in unmatched:
                unmatched.append(u)
        return out

    design.header_html = apply(design.header_html)
    design.footer_html = apply(design.footer_html)
    for b in design.blocks:
        if b.type == "text" and b.html:
            b.html = apply(b.html)
    return mapped, unmatched


def matcher_from_catalog(catalog) -> Matcher:
    """The same local fuzzy matcher, built from a SemanticCatalog (no AI)."""
    from app.services.ai_service import _local_match, _norm

    fields = list(catalog.field_index().values())
    candidates = [(f.ref, _norm(f.label), _norm(f.ref.split(".", 1)[-1])) for f in fields]
    date_refs = {f.ref for f in fields if f.type in (FieldType.DATE, FieldType.DATETIME)}
    for ref, phrases in catalog.synonyms_for_ref().items():
        if not ref or ref.startswith("metric."):
            continue
        tail = _norm(ref.split(".", 1)[-1])
        for phrase in phrases:
            candidates.append((ref, _norm(phrase), tail))

    def match(label: str) -> tuple[str | None, float]:
        ref, score = _local_match(label, candidates)
        # A short, generic word describing a date ("Date", "Expiry") is genuinely
        # ambiguous about WHICH date field is meant unless it names the field
        # exactly — unlike other field types, guessing wrong here silently puts
        # the wrong calendar date into a generated document. Longer/more specific
        # cues ("Contract End Date") are unaffected — only the short-word case.
        if ref in date_refs and score < 1.0 and len(_norm(label)) <= 4:
            return None, 0.0
        return ref, score

    return match


def map_word_fields_design(ai: AIService, ctx: TenantContext, design_json: dict) -> dict:
    """Deterministic: every leftover Word «Field» is scored by the catalogue matcher
    (labels + glossary). Confident hits become {{ref}}; the rest stay for Make dynamic.
    No AI, no letter-specific aliases."""
    design = DocumentDesign.model_validate(design_json)
    match, label_by_ref = ai.build_local_matcher(ctx)
    refs, unmatched = apply_word_fields_to_design(design, match)
    return {
        "design": design.model_dump(mode="json"),
        "review": [{"label": label_by_ref.get(r, r), "ref": r, "confidence": 1.0} for r in refs],
        "unmatched": unmatched,
    }


def bind_word_merge_fields(design: DocumentDesign, catalog) -> DocumentDesign:
    """Preview/generate: convert leftover Word merge fields using the catalogue."""
    apply_word_fields_to_design(design, matcher_from_catalog(catalog))
    return design


def _design(html: str) -> dict:
    return DocumentDesign(
        blocks=[DesignBlock(id=uuid.uuid4().hex[:8], type="text", html=html)]
    ).model_dump(mode="json")


def _name_ref(match: Matcher) -> str | None:
    """The best field for a person's name, for greetings/recipient lines."""
    for cue in ("employee full name", "full name", "employee name", "name"):
        ref, score = match(cue)
        if ref and score >= _MIN:
            return ref
    return None


def _cue_before(text: str, idx: int) -> str:
    """The likely field label just before position `idx` (last few content words)."""
    words = [w for w in re.findall(r"[A-Za-z]+", text[:idx]) if w.lower() not in _STOP]
    return " ".join(words[-3:])


def _tokenise_line(ln: str, match: Matcher, name_ref: str | None) -> tuple[str, list[str], list[str]]:
    """Return (line-with-tokens, mapped-refs, unmatched-cues) for one line.
    Tokens are inserted into the RAW line; the caller escapes it (braces survive)."""
    m = _FIELD_LINE.match(ln)
    if m and len(m.group(1).split()) <= 6:
        cue = m.group(1).strip()
        ref, score = match(cue)
        if ref and score >= _MIN:
            return f"{cue}: {_token(ref)}", [ref], []
        return ln, [], [cue]

    g = _GREETING.match(ln)
    if g and name_ref:
        return f"{g.group(1)} {_token(name_ref)},", [name_ref], []

    t = _TITLE.match(ln)
    if t and name_ref:
        return f"{t.group(1)} {_token(name_ref)}", [name_ref], []

    out, refs, unmatched = ln, [], []
    for am in _AMOUNT.finditer(ln):
        cue = _cue_before(ln, am.start())
        ref, score = match(cue) if cue else (None, 0.0)
        if ref and score >= _MIN:
            out = out.replace(am.group(0), _token(ref), 1)
            refs.append(ref)
        else:
            unmatched.append(am.group(0))
    return out, refs, unmatched


def _extract(match: Matcher, label_by_ref: dict[str, str], lines: list[str]) -> dict:
    name_ref = _name_ref(match)
    html_parts: list[str] = []
    review: list[dict] = []
    unmatched: list[str] = []
    seen: set[str] = set()
    for ln in lines:
        out, refs, un = _tokenise_line(ln, match, name_ref)
        for ref in refs:
            if ref not in seen:
                seen.add(ref)
                review.append({"label": label_by_ref.get(ref, ref), "ref": ref, "confidence": 1.0})
        unmatched.extend(u for u in un if u not in unmatched)
        html_parts.append(f"<p>{escape(out)}</p>" if out.strip() else "<p></p>")
    html = "".join(html_parts)
    html, word_refs, word_un = map_word_merge_fields(html, match)
    for ref in word_refs:
        if ref not in seen:
            seen.add(ref)
            review.append({"label": label_by_ref.get(ref, ref), "ref": ref, "confidence": 1.0})
    unmatched.extend(u for u in word_un if u not in unmatched)
    return {
        "design": _design(html),
        "review": review,
        "unmatched": unmatched,
        "note": "Mapped locally against your fields — no data was read or sent anywhere.",
    }


def build_design_from_sample(
    ai: AIService, ctx: TenantContext, content: bytes, filename: str, content_type: str,
) -> dict:
    match, label_by_ref = ai.build_local_matcher(ctx)
    if is_text_document(filename, content_type, content):
        lines = extract_lines(content, filename, content_type)
        if not lines:
            raise ValueError("Couldn’t read any content from that file.")
        return _extract(match, label_by_ref, lines)

    # Excel sample: each column header becomes a "Label: value" line to tokenise.
    cols = parse_document(content, filename, content_type).columns
    if not cols:
        raise ValueError("Couldn’t read any columns from that file.")
    return _extract(match, label_by_ref, [f"{c.header}: —" for c in cols])


# --------------------------------------------------------------------------- #
# Opt-in AI enhance — for the dynamic values the deterministic pass left behind.
# --------------------------------------------------------------------------- #
def ai_enhance_design(ai: AIService, ctx: TenantContext, design_json: dict) -> dict:
    """Run the AI extraction over the CURRENT design's visible text and tokenise any
    per-recipient values it finds that aren't already bound. Slower (one LLM call) —
    called only when the user clicks 'Smart map with AI'. Returns the updated design +
    the newly-mapped fields + any dynamic spans it still couldn't map."""
    design = DocumentDesign.model_validate(design_json)
    match, label_by_ref = ai.build_local_matcher(ctx)
    # include_bare=False: this design isn't known to have come from a Word
    # upload, so don't run the Name_with_underscores pass here — it also
    # matches ordinary prose (an email address, a reference code).
    word_refs, word_un = apply_word_fields_to_design(design, match, include_bare=False)
    text_blocks = [b for b in design.blocks if b.type == "text" and b.html]
    # Visible text WITHOUT existing tokens (so the AI maps only what's still literal).
    plain = "\n".join(
        unescape(_TAG.sub(" ", _EXISTING_TOKEN.sub(" ", b.html or ""))).strip()
        for b in text_blocks
    ).strip()
    # Strip any leftover unmatched «Field»/<<Field>>/[Field] wrappers too — they're
    # template syntax, not real values, and would confuse the AI's extraction.
    plain = _MARK_WRAPPED.sub(" ", plain)
    word_review = [{"label": label_by_ref.get(r, r), "ref": r, "confidence": 1.0} for r in word_refs]
    if not re.sub(r"\s+", "", plain):
        return {
            "design": design.model_dump(mode="json"),
            "review": word_review,
            "unmatched": word_un,
        }

    replacements = ai.extract_letter_replacements(ctx, plain)

    review: list[dict] = list(word_review)
    unmatched: list[str] = list(word_un)
    seen: set[str] = set(word_refs)
    # Longest spans first so a short value inside a longer one doesn't clobber it.
    for r in sorted(replacements, key=lambda x: len(x["text"]), reverse=True):
        span = r["text"]
        if not span:
            continue
        if r["ref"]:
            hit = False
            for b in text_blocks:
                if span in (b.html or ""):
                    b.html = b.html.replace(span, _token(r["ref"]))
                    hit = True
            if hit and r["ref"] not in seen:
                seen.add(r["ref"])
                review.append({"label": r.get("label") or label_by_ref.get(r["ref"], r["ref"]),
                               "ref": r["ref"], "confidence": 1.0})
        elif span not in unmatched:
            unmatched.append(span)
    return {"design": design.model_dump(mode="json"), "review": review, "unmatched": unmatched}
