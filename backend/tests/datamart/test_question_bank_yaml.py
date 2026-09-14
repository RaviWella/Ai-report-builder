"""Structure checks for datamart_question_bank.yaml (no warehouse)."""
from pathlib import Path

import yaml


def _load_items():
    path = Path(__file__).resolve().parents[2] / "tools" / "datamart_question_bank.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    items = []
    for section, entries in raw.items():
        if section == "meta" or not isinstance(entries, list):
            continue
        for entry in entries:
            if isinstance(entry, dict) and entry.get("question"):
                items.append({**entry, "section": section})
    return raw, items


def test_question_bank_meta_matches_entries():
    raw, items = _load_items()
    meta = raw["meta"]
    assert meta["question_count"] == len(items)
    assert meta["set_count"] * meta["set_size"] >= len(items)
    assert len(items) >= 60


def test_each_entry_has_question_and_expect_tables():
    _, items = _load_items()
    for entry in items:
        assert entry["question"].strip()
        assert entry.get("expect_tables")
        assert isinstance(entry["expect_tables"], list)


def test_each_section_has_six_questions():
    raw, _ = _load_items()
    set_size = int(raw["meta"]["set_size"])
    for section, entries in raw.items():
        if section == "meta" or not isinstance(entries, list):
            continue
        assert len(entries) == set_size, (
            f"{section} should have {set_size} questions, got {len(entries)}"
        )
