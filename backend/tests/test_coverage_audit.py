"""Coverage-audit summary classification (pure — no DB)."""

from app.services.coverage_audit import FieldCoverage, _summary


def _fc(ref, status, cov=None):
    return FieldCoverage(ref, ref, "employee", "t", "c", 100, 0, cov, status)


def test_summary_counts_and_gaps():
    results = [
        _fc("employee.full_name", "ok", 1.0),
        _fc("employee.age", "ok", 0.98),
        _fc("employee.department", "empty", 0.0),
        _fc("employee.position", "empty", 0.0),
        _fc("employee.gone", "missing"),
        _fc("employee.weird", "error"),
    ]
    s = _summary(results)
    assert s["fields"] == 6
    assert s["ok"] == 2
    assert s["empty"] == 2
    assert s["missing"] == 1
    assert s["errored"] == 1
    # The trust risk: empty + missing fields a report could still select.
    assert set(s["data_capture_gaps"]) == {
        "employee.department", "employee.position", "employee.gone"
    }
