"""Legacy Word .doc sample letters are read as flowing text (not Excel)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ingestion.document_parser import (
    _is_word,
    extract_lines,
    is_text_document,
    parse_document,
)
from app.ingestion.word_doc import _clean_binary_text, is_legacy_word

_DOC = Path(__file__).parent / "fixtures" / "letter_sample.doc"


def test_doc_is_a_text_letter_sample():
    assert is_legacy_word("offer.doc", "")
    assert is_legacy_word("offer.DOC", "application/msword")
    assert _is_word("offer.doc", "")
    assert is_text_document("offer.doc", "application/msword")
    assert not is_legacy_word("offer.docx", "")
    assert not is_text_document("sheet.xlsx", "")


def test_doc_detected_from_ole2_bytes_without_filename():
    content = _DOC.read_bytes()
    assert is_legacy_word("", "", content)
    assert is_text_document("", "", content)


def test_extract_lines_reads_doc_paragraphs():
    lines = extract_lines(_DOC.read_bytes(), "letter.doc", "application/msword")
    assert any("Dear Display_Name" in ln for ln in lines)
    assert any("Acceptance of Resignation" in ln for ln in lines)
    assert any("Employee Name" in ln and "Jane Doe" in ln for ln in lines)
    assert any("Designation" in ln and "Analyst" in ln for ln in lines)


def test_parse_document_does_not_treat_doc_as_spreadsheet():
    with pytest.raises(ValueError, match="isn't in column form"):
        parse_document(_DOC.read_bytes(), "letter.doc", "application/msword")


def test_mergefield_codes_become_guillemet_marks():
    raw = "Dear \x13 MERGEFIELD Display_Name \x14«Display_Name»\x15,\nTitle: Analyst"
    cleaned = _clean_binary_text(raw)
    assert "«Display_Name»" in cleaned
    assert "MERGEFIELD" not in cleaned
