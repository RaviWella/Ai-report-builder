"""_require_publishable — BR-T-01/02 (name/category) plus the letter record-key
rule: a letter can't publish without 'One per record' set. No default is ever
invented here (see document_design.py) — the designer must pick it explicitly.
"""

from __future__ import annotations

import pytest

from app.domain.document_design import DocumentDesign
from app.services.document_service import _require_publishable


def test_draft_never_requires_record_key():
    _require_publishable(False, "A Letter", "General", "letter", None)  # no raise


def test_letter_publish_without_record_key_is_blocked():
    with pytest.raises(ValueError, match="One per record"):
        _require_publishable(True, "A Letter", "General", "letter", DocumentDesign())


def test_letter_publish_with_record_key_is_allowed():
    design = DocumentDesign(record_key_ref="employee.epf_no")
    _require_publishable(True, "A Letter", "General", "letter", design)  # no raise


def test_non_letter_publish_does_not_require_record_key():
    _require_publishable(True, "A Report", "General", "report", None)  # no raise
    _require_publishable(True, "An Email", "General", "email", DocumentDesign())  # no raise


def test_publish_still_requires_name_and_category():
    with pytest.raises(ValueError, match="name"):
        _require_publishable(True, "", "General", "report", None)
    with pytest.raises(ValueError, match="category"):
        _require_publishable(True, "A Report", "", "report", None)
