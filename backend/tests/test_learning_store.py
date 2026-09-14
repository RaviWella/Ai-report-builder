"""Unit tests for the canonical-intent store's keying — the pure, DB-free parts.

These guarantee the consistency property: phrasings that mean the same thing
normalise to one key (so they replay one saved spec), while phrasings that ask for
different data stay distinct.
"""

from app.services.learning_store import LearningStore

pk = LearningStore.phrase_key
sig = LearningStore.signature


def test_noise_and_word_order_collapse_to_one_key():
    keys = {
        pk("headcount by department"),
        pk("show me the headcount by department please"),
        pk("department-wise headcount"),
        pk("Headcount, by Department"),
    }
    assert len(keys) == 1


def test_different_grouping_stays_distinct():
    assert pk("headcount by department") != pk("headcount by grade")


def test_filter_word_is_meaningful_not_collapsed():
    # "active" changes which data is asked for, so it must survive normalisation.
    assert pk("active employee count") != pk("employee count")


def test_signature_is_order_independent_for_same_spec():
    a = {
        "entity": "employee",
        "fields": [{"ref": "employee.full_name"}, {"ref": "employee.department"}],
        "filters": [], "group_by": [], "aggregations": [],
    }
    b = {
        "entity": "employee",
        "fields": [{"ref": "employee.department"}, {"ref": "employee.full_name"}],
        "filters": [], "group_by": [], "aggregations": [],
    }
    assert sig(a) == sig(b)


def test_signature_differs_when_data_differs():
    base = {"entity": "employee", "fields": [{"ref": "employee.full_name"}],
            "filters": [], "group_by": [], "aggregations": []}
    withfilter = {**base, "filters": [{"ref": "employee.status", "op": "eq", "value": "active"}]}
    assert sig(base) != sig(withfilter)


def test_empty_phrase_key_is_blank():
    assert pk("the of and by") == ""
