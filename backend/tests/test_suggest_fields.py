"""Unit tests for the field-suggestion ranker — the pure, DB-free part. Guarantees
a column that didn't auto-map gets a sensible, best-first shortlist to choose from.
"""

from app.services.ai_service import _norm, _rank_candidates


def _cands(pairs):
    # (ref, label) -> the (ref, norm_label, norm_ref_tail) tuples the ranker takes.
    return [(ref, _norm(label), _norm(ref.split(".", 1)[-1])) for ref, label in pairs]


def test_returns_best_first_and_limited():
    cands = _cands([
        ("employee.location", "Location"),
        ("employee.position", "Position"),
        ("employee.emp_no", "Employee Number"),
    ])
    out = _rank_candidates("Punch In Location", cands, limit=2)
    assert len(out) == 2
    assert out[0][0] == "employee.location"  # strongest match first
    assert out[0][1] >= out[1][1]            # sorted by score descending


def test_dedupes_to_best_score_per_ref():
    # Two candidate rows for the same ref (e.g. label + a glossary alias) collapse
    # to one entry carrying the higher score.
    cands = _cands([("employee.emp_no", "Employee Number")]) + [
        ("employee.emp_no", _norm("Staff Badge Code"), _norm("emp_no")),
    ]
    out = _rank_candidates("Staff Badge Code", cands, limit=5)
    refs = [r for r, _ in out]
    assert refs.count("employee.emp_no") == 1


def test_blank_header_yields_no_suggestions():
    assert _rank_candidates("   ", _cands([("employee.location", "Location")]), limit=3) == []


def test_dictionary_synonym_maps_heading_to_field():
    # A dictionary synonym row (e.g. "in-hand salary" -> payroll.net) lets a heading
    # that doesn't match the label at all still rank onto the right field.
    cands = _cands([("payroll.net", "Net Salary"), ("payroll.gross", "Gross Salary")]) + [
        ("payroll.net", _norm("in-hand salary"), _norm("net")),
        ("payroll.net", _norm("take home"), _norm("net")),
    ]
    out = _rank_candidates("In-Hand Salary", cands, limit=3)
    assert out[0][0] == "payroll.net"  # synonym wins over the literal labels
