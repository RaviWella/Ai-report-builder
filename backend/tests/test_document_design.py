"""Canvas design model + render helpers — pure logic, no DB/datamart."""

from __future__ import annotations

from app.domain.document_design import (
    DesignBlock,
    DesignColumn,
    DocumentDesign,
    extract_tokens,
    parse_token,
)
from app.services.document_design_render import (
    compose_record_html,
    substitute_tokens,
)
from app.services.letter_html import is_faint_color, sanitize_letter_html


def test_extract_tokens_finds_refs_with_and_without_spaces():
    assert extract_tokens("Dear {{employee.name}}, net {{ payroll.net }}") == [
        "employee.name",
        "payroll.net",
    ]
    assert extract_tokens(None) == []
    assert extract_tokens("no tokens here") == []


def test_value_refs_collects_text_field_and_table_refs_unique_ordered():
    design = DocumentDesign(
        blocks=[
            DesignBlock(id="t1", type="text", html="Hi {{employee.name}} — {{employee.name}}"),
            DesignBlock(id="f1", type="field", ref="payroll.net_salary", label="Net"),
            DesignBlock(
                id="tb1", type="table",
                columns=[DesignColumn(ref="pay.item"), DesignColumn(ref="pay.amount")],
            ),
        ],
    )
    assert design.value_refs() == [
        "employee.name",
        "payroll.net_salary",
        "pay.item",
        "pay.amount",
    ]


def test_substitute_tokens_escapes_values_but_not_markup():
    row = {"employee.name": "A&B <x>", "payroll.net": 1234.5}
    out = substitute_tokens("<b>Dear {{employee.name}}</b>: {{payroll.net}}", row)
    # markup preserved, value escaped, number grouped
    assert "<b>Dear" in out
    assert "A&amp;B &lt;x&gt;" in out
    assert "1,234.50" in out


def test_compose_record_html_renders_field_and_signature_blocks():
    design = DocumentDesign(
        blocks=[
            DesignBlock(id="f1", type="field", ref="salary", label="Salary", prefix="Rs. "),
            DesignBlock(id="s1", type="signature", label="Authorised Signatory"),
            DesignBlock(id="d1", type="divider"),
        ],
    )
    html = compose_record_html(design, {"salary": 5000})
    assert "Rs. 5,000.00" in html
    assert "Authorised Signatory" in html
    assert "blk-divider" in html


def test_missing_token_value_renders_empty_not_literal():
    out = substitute_tokens("X={{missing.ref}}Y", {})
    assert out == "X=Y"


def test_faint_word_merge_colours_are_detected():
    assert is_faint_color("#F2F2F2")
    assert is_faint_color("#BFBFBF")
    assert is_faint_color("white")
    assert is_faint_color("silver")
    assert is_faint_color("rgb(255, 255, 255)")
    assert is_faint_color("rgba(0, 0, 0, 0.15)")
    assert not is_faint_color("#1F2937")
    assert not is_faint_color("black")
    assert not is_faint_color("#007499")


def test_sanitize_letter_html_drops_faint_color_keeps_other_styles():
    html = (
        '<p>HRIS: <span style="color:#F2F2F2;font-weight:bold">«HRIS»</span></p>'
        '<p>Dear <span style="color: #BFBFBF">{{attendance_daily.display_name}}</span></p>'
        '<p><span style="color:#1F2937">Acceptance of Resignation</span></p>'
    )
    out = sanitize_letter_html(html)
    assert "«HRIS»" in out
    assert "{{attendance_daily.display_name}}" in out
    assert "color:#F2F2F2" not in out
    assert "color: #BFBFBF" not in out
    assert "font-weight:bold" in out
    assert "color:#1F2937" in out


def test_record_key_ref_is_never_guessed():
    """No default is invented for a blank 'One per record' — the ref must come
    from the designer's own pick on the tenant's catalogue, never a hardcoded
    HR-specific guess (refs aren't the same across tenants)."""
    blank = DocumentDesign()
    assert blank.record_key_ref is None

    chosen = DocumentDesign(record_key_ref="employee.epf_no")
    assert chosen.record_key_ref == "employee.epf_no"


def test_substitute_tokens_after_faint_color_strip():
    html = '<span style="color:#EEEEEE">Dear {{employee.name}}</span>'
    out = substitute_tokens(html, {"employee.name": "Amara"})
    assert "Amara" in out
    assert "color:#EEEEEE" not in out
    assert "{{employee.name}}" not in out


def test_parse_token_splits_ref_and_value_map():
    assert parse_token("employee.gender") == ("employee.gender", {})
    assert parse_token("employee.gender|Male=he|Female=she") == (
        "employee.gender", {"Male": "he", "Female": "she"},
    )
    assert parse_token("not a ref|x=y") is None  # ref part isn't ref-shaped


def test_extract_tokens_ignores_value_map_but_keeps_the_ref():
    html = "{{employee.gender|Male=he|Female=she}} said hello"
    assert extract_tokens(html) == ["employee.gender"]


def test_mapped_token_substitutes_by_the_record_s_own_value():
    html = (
        "Please ask {{employee.gender|Male=him|Female=her|default=them}} to sign, "
        "as {{employee.gender|Male=he|Female=she|default=they}} confirmed."
    )
    out_m = substitute_tokens(html, {"employee.gender": "Male"})
    assert "ask him to sign" in out_m
    assert "as he confirmed" in out_m

    out_f = substitute_tokens(html, {"employee.gender": "Female"})
    assert "ask her to sign" in out_f
    assert "as she confirmed" in out_f

    out_other = substitute_tokens(html, {"employee.gender": "Non-binary"})
    assert "ask them to sign" in out_other
    assert "as they confirmed" in out_other


def test_mapped_token_falls_back_to_raw_value_without_a_default():
    out = substitute_tokens("{{employee.gender|Male=he|Female=she}}", {"employee.gender": "Other"})
    assert out == "Other"
