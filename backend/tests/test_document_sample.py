"""Sample-letter -> canvas design: DETERMINISTIC (no AI). Prose stays static; dynamic
values (Label: value, Dear <name>, inline amounts) become {{tokens}} via the local
fuzzy field matcher."""

from __future__ import annotations

import re

import app.services.document_sample as ds


class _StubAI:
    """A local matcher over a tiny catalogue — mirrors AIService.build_local_matcher
    AND matcher_from_catalog's date-type ambiguity guard (see document_sample.py):
    a short, generic cue ('Date') must name a date field exactly, since guessing
    wrong there silently puts the wrong calendar date into a document. Other
    field types (including short ones like 'Name') use the normal fuzzy score."""

    _TABLE = {
        "employee full name": ("employee.full_name", 1.0),
        "full name": ("employee.full_name", 1.0),
        "employee name": ("employee.full_name", 0.95),
        "name": ("employee.full_name", 0.92),  # containment tier, same as real _local_match
        "display name": ("employee.display_name", 1.0),
        "basic salary": ("payroll.basic", 0.95),
        "basic": ("payroll.basic", 0.9),
        "designation": ("employee.designation", 0.95),
        "date of birth": ("employee.date_of_birth", 1.0),
        "date": ("employee.date_of_birth", 0.92),  # substring trap — must NOT win for «Date»
        "employee number": ("employee.emp_no", 1.0),
        "emp no": ("employee.emp_no", 0.95),
        "loan deduction": ("payroll.loan_deduction", 0.95),
        "loan": ("payroll.loan_deduction", 0.85),
    }
    _LABELS = {"employee.full_name": "Full Name", "payroll.basic": "Basic Salary",
               "employee.designation": "Designation"}
    _DATE_REFS = {"employee.date_of_birth"}

    def build_local_matcher(self, ctx):
        def match(label):
            key = " ".join(label.lower().split())
            ref, score = self._TABLE.get(key, (None, 0.0))
            if not ref:
                # cheap containment so 'salary basic' etc still resolve
                for k, v in self._TABLE.items():
                    if k in key or key in k:
                        ref, score = v
                        break
            if ref in self._DATE_REFS and score < 1.0 and len(re.sub(r"[^a-z0-9]", "", key)) <= 4:
                return None, 0.0
            return ref, score
        return match, self._LABELS


def test_label_value_lines_become_tokens(monkeypatch):
    lines = ["Employee Name: John Perera", "Basic Salary: 50,000.00", "Favourite Colour: Blue"]
    monkeypatch.setattr(ds, "is_text_document", lambda *a, **k: True)
    monkeypatch.setattr(ds, "extract_lines", lambda *a, **k: lines)
    out = ds.build_design_from_sample(_StubAI(), ctx=None, content=b"x", filename="l.pdf", content_type="application/pdf")
    html = out["design"]["blocks"][0]["html"]
    assert "{{employee.full_name}}" in html and "{{payroll.basic}}" in html
    assert "John Perera" not in html and "50,000.00" not in html
    assert "Favourite Colour" in out["unmatched"]


def test_greeting_and_inline_amount(monkeypatch):
    lines = [
        "Dear George Alexander,",
        "you will receive a consolidated Basic Salary of Rs.45000.00 per month.",
        "We trust you will have a long career with us.",
    ]
    monkeypatch.setattr(ds, "is_text_document", lambda *a, **k: True)
    monkeypatch.setattr(ds, "extract_lines", lambda *a, **k: lines)
    out = ds.build_design_from_sample(_StubAI(), ctx=None, content=b"x", filename="l.pdf", content_type="application/pdf")
    html = out["design"]["blocks"][0]["html"]
    assert "Dear {{employee.full_name}}," in html          # greeting name
    assert "{{payroll.basic}}" in html                      # inline amount mapped via preceding words
    assert "Rs.45000.00" not in html and "George Alexander" not in html
    assert "long career with us" in html                    # static boilerplate preserved


def test_empty_sample_raises(monkeypatch):
    monkeypatch.setattr(ds, "is_text_document", lambda *a, **k: True)
    monkeypatch.setattr(ds, "extract_lines", lambda *a, **k: [])
    try:
        ds.build_design_from_sample(_StubAI(), ctx=None, content=b"", filename="x.pdf", content_type="application/pdf")
        assert False, "expected ValueError"
    except ValueError:
        pass


class _EnhanceAI(_StubAI):
    def extract_letter_replacements(self, ctx, text):
        return [
            {"text": "George Alexander", "ref": "employee.full_name", "label": "Full Name"},
            {"text": "Colombo 05", "ref": None, "label": None},  # dynamic but unmapped
        ]


def test_ai_enhance_tokenises_current_design_and_keeps_existing_tokens():
    design = {
        "page_size": "A4", "orientation": "portrait", "margin_mm": 20, "blocks": [
            {"id": "b1", "type": "text",
             "html": "<p>Dear George Alexander,</p><p>Office: Colombo 05</p><p>Salary {{payroll.basic}}</p>"},
        ],
    }
    out = ds.ai_enhance_design(_EnhanceAI(), ctx=None, design_json=design)
    html = out["design"]["blocks"][0]["html"]
    assert "{{employee.full_name}}" in html          # newly mapped
    assert "{{payroll.basic}}" in html               # existing token preserved
    assert "George Alexander" not in html
    assert {r["ref"] for r in out["review"]} == {"employee.full_name"}
    assert "Colombo 05" in out["unmatched"]


def test_word_merge_fields_become_tokens():
    match, _ = _StubAI().build_local_matcher(None)
    html = (
        "<p>HRIS: «HRIS»</p>"
        "<p>«Title» . «Name_»</p>"
        "<p>Dear {{employee.full_name}},</p>"
        "<p>your «Designation» — loan «Staff_Loan_to_be_settle» «AutoMergeField»</p>"
    )
    out, refs, unmatched = ds.map_word_merge_fields(html, match)
    assert "{{employee.full_name}}" in out          # «Name_» → catalogue "name"
    assert "{{employee.designation}}" in out
    assert "{{payroll.loan_deduction}}" in out      # cue contains "loan"
    assert "«HRIS»" in out                          # no catalogue/glossary hit
    assert "«AutoMergeField»" in out
    assert "employee.full_name" in refs
    assert any(u.lower() == "title" for u in unmatched)


def test_short_date_mark_does_not_become_date_of_birth():
    match, _ = _StubAI().build_local_matcher(None)
    out, refs, unmatched = ds.map_word_merge_fields("<p>«Date»</p>", match)
    assert "{{employee.date_of_birth}}" not in out
    assert "«Date»" in out
    assert "employee.date_of_birth" not in refs
    assert any(u.lower() == "date" for u in unmatched)


def test_merge_name_wrappers_are_equivalent():
    match, _ = _StubAI().build_local_matcher(None)
    for html in (
        "<p>«Designation»</p>",
        "<p><<Designation>></p>",
        "<p>[Designation]</p>",
        "<p>Prsent_Designation_</p>",
    ):
        out, refs, _ = ds.map_word_merge_fields(html, match)
        assert "{{employee.designation}}" in out, html
        assert "employee.designation" in refs


def test_mapped_token_survives_a_word_field_mapping_rerun():
    """An already-resolved {{ref|value=text|...}} (a gendered pronoun token, say)
    must not be mistaken for a new, unmatched Word cue on a second mapping pass."""
    match, _ = _StubAI().build_local_matcher(None)
    html = "<p>{{employee.designation|Manager=leads|Analyst=supports}}</p>"
    out, _refs, unmatched = ds.map_word_merge_fields(html, match)
    assert out == html
    assert unmatched == []


def test_ascii_wrapper_matches_html_escaped_form():
    """A rich-text editor always entity-escapes literal < / > in text nodes, so
    a marker typed/pasted through the normal editor flow is stored as
    &lt;&lt;...&gt;&gt;, never literal <<...>> — detection must match both."""
    match, _ = _StubAI().build_local_matcher(None)
    out, refs, _ = ds.map_word_merge_fields("<p>&lt;&lt;Designation&gt;&gt;</p>", match)
    assert "{{employee.designation}}" in out
    assert "employee.designation" in refs


def test_ai_enhance_does_not_swallow_plain_underscore_text():
    """include_bare must be off for the generic AI-enhance path — this design
    isn't known to have come from a Word upload, so an ordinary underscore_joined
    word in typed prose (an email, a reference code) must stay literal, not get
    silently swallowed into a merge token."""
    design = {
        "page_size": "A4", "orientation": "portrait", "margin_mm": 20, "blocks": [
            {"id": "b1", "type": "text", "html": "<p>Contact jane_doe@example.com for ABC_1234.</p>"},
        ],
    }
    out = ds.ai_enhance_design(_EnhanceAI(), ctx=None, design_json=design)
    html = out["design"]["blocks"][0]["html"]
    assert "jane_doe@example.com" in html
    assert "ABC_1234" in html


def test_word_paste_entities_and_typo_suffix_still_map():
    match, _ = _StubAI().build_local_matcher(None)
    html = (
        "<p>Dear &laquo;Calling_Name&raquo;,</p>"
        "<p>«Prsent_Designation_» «New_Designation» «HRIS»</p>"
        "<p>«Name_with_intials_»</p>"
    )
    out, refs, unmatched = ds.map_word_merge_fields(html, match)
    assert "{{employee.designation}}" in out
    assert "{{employee.full_name}}" in out or "{{employee.display_name}}" in out
    assert "«HRIS»" in out
    assert "employee.designation" in refs


def test_map_word_fields_design_uses_catalogue_matcher():
    design = {
        "page_size": "A4", "orientation": "portrait", "margin_mm": 20, "blocks": [
            {"id": "b1", "type": "text",
             "html": "<p>Dear «Display_Name»,</p><p>«Designation» «HRIS»</p>"},
        ],
    }
    out = ds.map_word_fields_design(_StubAI(), ctx=None, design_json=design)
    html = out["design"]["blocks"][0]["html"]
    assert "{{employee.display_name}}" in html
    assert "{{employee.designation}}" in html
    assert "«HRIS»" in html
    assert {r["ref"] for r in out["review"]} >= {"employee.display_name", "employee.designation"}
