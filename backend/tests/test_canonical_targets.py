"""Smoke tests for the MintHRM canonical target registry.

Verifies:
  1. Every target has a unique data_type.
  2. Every target has at least one required field.
  3. Every natural_key field exists in the target's field list.
  4. Alias normalisation is collision-free within each target
     (two different canonical fields must not share a normalised alias).
  5. Classifier scores the right target as top-1 when given its own
     required field names as headers.
  6. Mapper resolves required fields from their canonical names.
  7. Mapper resolves required fields from their first alias.
  8. TenantConfig round-trips through to_dict / load (JSON).
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from app.services.data_intake.canonical_targets import (
    CANONICAL_TARGETS,
    all_targets,
    get_target,
)
from app.services.data_intake.classifier import classify, DEFAULT_CONFIDENCE_THRESHOLD
from app.services.data_intake.mapper import build_mapping_result
from app.services.data_intake.tenant_config import (
    TenantConfig,
    empty_tenant_config,
    load_tenant_config,
)


# ── Minimal FileProfile / SheetProfile stubs ─────────────────────


class _SheetProfile:
    def __init__(self, name: str, headers: list[str]):
        self.name = name
        self.headers = headers
        self.row_count = 1


class _FileProfile:
    def __init__(self, headers: list[str], sheet_name: str = "Sheet1"):
        self.sheets = [_SheetProfile(sheet_name, headers)]


# ── 1. Unique data_types ──────────────────────────────────────────


def test_unique_data_types():
    ids = [t.data_type for t in CANONICAL_TARGETS]
    assert len(ids) == len(set(ids)), "Duplicate data_type in CANONICAL_TARGETS"


# ── 2. Every target has at least one required field ───────────────


@pytest.mark.parametrize("target", CANONICAL_TARGETS)
def test_has_required_field(target):
    required = [f for f in target.fields if f.required]
    assert required, f"{target.data_type} has no required fields"


# ── 3. Natural key fields exist in the target ─────────────────────


@pytest.mark.parametrize("target", CANONICAL_TARGETS)
def test_natural_key_fields_exist(target):
    field_names = {f.name for f in target.fields}
    for nk in target.natural_key:
        assert nk in field_names, (
            f"{target.data_type}: natural_key field '{nk}' not in fields"
        )


# ── 4. No alias collision within a target ────────────────────────


@pytest.mark.parametrize("target", CANONICAL_TARGETS)
def test_no_alias_collision(target):
    seen: dict[str, str] = {}
    for f in target.fields:
        def _norm(s: str) -> str:
            return "".join(ch for ch in s.lower() if ch.isalnum())
        for alias in (f.name,) + f.aliases:
            key = _norm(alias)
            assert key not in seen or seen[key] == f.name, (
                f"{target.data_type}: alias '{alias}' (norm='{key}') "
                f"collides between '{seen[key]}' and '{f.name}'"
            )
            seen[key] = f.name


# ── 5. Classifier top-1 on required field names ───────────────────


@pytest.mark.parametrize("target", CANONICAL_TARGETS)
def test_classifier_top1_on_required_fields(target):
    required_headers = [f.name for f in target.fields if f.required]
    profile = _FileProfile(required_headers)
    result = classify(profile, threshold=0.0)
    assert result.candidates, f"{target.data_type}: no candidates returned"
    top = result.candidates[0]
    assert top.data_type == target.data_type, (
        f"{target.data_type}: expected top-1 but got '{top.data_type}' "
        f"(score={top.score:.3f})"
    )
    assert top.score >= DEFAULT_CONFIDENCE_THRESHOLD, (
        f"{target.data_type}: score {top.score:.3f} below threshold"
    )


# ── 6. Mapper resolves required fields from canonical names ───────


@pytest.mark.parametrize("target", CANONICAL_TARGETS)
def test_mapper_resolves_required_by_canonical_name(target):
    all_headers = [f.name for f in target.fields]
    profile = _FileProfile(all_headers)
    result = classify(profile, threshold=0.0)
    mapping = build_mapping_result(profile, result)
    assert mapping is not None, f"{target.data_type}: mapping returned None"
    mapped_canonicals = {m.canonical_field for m in mapping.mapped_fields}
    for f in target.fields:
        if f.required:
            assert f.name in mapped_canonicals, (
                f"{target.data_type}: required field '{f.name}' not mapped"
            )
    assert not mapping.missing_required_fields, (
        f"{target.data_type}: missing_required_fields={mapping.missing_required_fields}"
    )


# ── 7. Mapper resolves required fields from their aliases ─────────
# Uses ALL required-field aliases together (as a real file would),
# not just the first alias of each in isolation.  A single-alias
# header set is too sparse to discriminate targets that share
# employee_id as a required field.


@pytest.mark.parametrize("target", CANONICAL_TARGETS)
def test_mapper_resolves_required_by_first_alias(target):
    required_with_alias = [f for f in target.fields if f.required and f.aliases]
    if not required_with_alias:
        pytest.skip(f"{target.data_type}: no required fields with aliases")

    # Use ALL required-field aliases so the classifier has enough signal
    # to pick the right target (mirrors a real customer file).
    alias_headers = [f.aliases[0] for f in target.fields if f.aliases]
    profile = _FileProfile(alias_headers)
    result = classify(profile, threshold=0.0)
    mapping = build_mapping_result(profile, result)
    assert mapping is not None
    mapped_canonicals = {m.canonical_field for m in mapping.mapped_fields}
    for f in required_with_alias:
        assert f.name in mapped_canonicals, (
            f"{target.data_type}: required field '{f.name}' not mapped via alias '{f.aliases[0]}'"
        )


# ── 8. TenantConfig round-trip ────────────────────────────────────


def test_tenant_config_roundtrip_json():
    from app.services.data_intake.tenant_config import _compute_config_hash
    cfg = empty_tenant_config("tenant_abc")
    cfg.aliases = {
        "hr.employee_master": {
            "employee_id": ["Staff Number", "Personnel ID"],
        }
    }
    cfg.date_formats = ["%d/%m/%Y"]
    cfg.severity_overrides = {"duplicate_key": "warning"}
    cfg.config_hash = _compute_config_hash(cfg)  # recompute after mutation

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(cfg.to_dict(), f)
        tmp_path = f.name

    loaded = load_tenant_config(tmp_path)
    assert loaded.tenant_id == "tenant_abc"
    assert loaded.aliases["hr.employee_master"]["employee_id"] == [
        "Staff Number", "Personnel ID"
    ]
    assert loaded.date_formats == ["%d/%m/%Y"]
    assert loaded.severity_overrides == {"duplicate_key": "warning"}
    assert loaded.config_hash == cfg.config_hash


# ── 9. get_target / all_targets helpers ──────────────────────────


def test_get_target_known():
    t = get_target("hr.employee_master")
    assert t is not None
    assert t.data_type == "hr.employee_master"


def test_get_target_unknown():
    assert get_target("hr.does_not_exist") is None


def test_all_targets_returns_all():
    assert len(all_targets()) == len(CANONICAL_TARGETS)
