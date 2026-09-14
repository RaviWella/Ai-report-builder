"""Unit test for the field-request key — the pure, DB-free part. Guarantees repeat
requests for the "same" heading collapse to one gap-list entry (bumped, not duped).
"""

from app.services.field_request_store import FieldRequestStore

hk = FieldRequestStore.header_key


def test_same_heading_variants_collapse_to_one_key():
    assert hk("Actual In Time") == hk("actual  in time") == hk("Actual In Time.")


def test_distinct_headings_stay_distinct():
    assert hk("Actual In Time") != hk("Actual Out Time")


def test_blank_heading_is_empty():
    assert hk("  ") == ""
