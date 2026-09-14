"""The AI rule-report chat's system prompt is built from real, working example
specs on disk (never a hand-copied string that can drift) — these tests pin
that behaviour."""

import json

from app.services.rule_report_ai import prompt as prompt_mod


def test_examples_dir_has_real_valid_specs():
    from app.domain.rule_report import RuleReportSpec

    examples = prompt_mod._load_examples()
    assert len(examples) >= 3
    for ex in examples:
        RuleReportSpec.model_validate(ex)  # raises if any bundled example rots


def test_system_prompt_documents_the_whitelisted_functions():
    text = prompt_mod.build_system_prompt()
    for fn in ("greatest", "least", "max", "min", "coalesce", "abs", "round", "time", "hours_between"):
        assert fn in text


def test_system_prompt_embeds_every_example_as_json():
    text = prompt_mod.build_system_prompt()
    for ex in prompt_mod._load_examples():
        assert json.dumps(ex["name"]) in text


def test_system_prompt_is_deterministic():
    assert prompt_mod.build_system_prompt() == prompt_mod.build_system_prompt()
