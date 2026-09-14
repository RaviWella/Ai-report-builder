"""Unit tests for the learned column-mapping store's keying — the pure, DB-free
part. These guarantee the auto-correct property: headers that are the "same"
(case / punctuation / spacing) collapse to one memory key, while order-meaningful
headers (Punch In vs Punch Out) stay distinct so they can map to different fields.
"""

from app.services.column_mapping_store import ColumnMappingStore

hk = ColumnMappingStore.header_key


def test_case_punctuation_and_spacing_collapse_to_one_key():
    assert hk("EMP No") == hk("emp  no.") == hk("Emp No") == hk("emp_no")


def test_order_meaningful_headers_stay_distinct():
    assert hk("Punch In Location") != hk("Punch Out Location")
    assert hk("Actual In Time") != hk("Actual Out Time")


def test_blank_header_yields_empty_key():
    # An empty key is never stored (remember() no-ops), so upload noise can't
    # create a junk memory entry.
    assert hk("   ") == ""
    assert hk("!!!") == ""
