"""rule_report is recognised as its own template kind (tabular, view/excel/pdf)."""
from app.services.template_kind import allowed_formats, kind_of


def test_rule_report_kind_detected():
    ps = {"kind": "rule_report", "spec": {}}
    assert kind_of(ps) == "rule_report"
    assert set(allowed_formats(ps)) == {"view", "excel", "pdf"}


def test_unknown_kind_falls_back_to_report():
    assert kind_of({"kind": "wat"}) == "report"
    assert kind_of(None) == "report"
    assert kind_of({}) == "report"
