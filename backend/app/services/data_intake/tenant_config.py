"""Per-tenant configuration for the MintHRM Data Intake layer.

Loads tenant-specific overrides from JSON or YAML.

``TenantConfig.aliases`` is shaped exactly like the mapper's
``TenantOverrides`` parameter so callers can wire it in directly.

``config_hash`` is sha256 over the canonical-JSON of the config content
(file path excluded; ``config_hash`` field itself excluded so the hash
is stable across reloads).

Ported from mint-analytics data_intake/tenant_config.py — unchanged.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

DEFAULT_BALANCE_TOLERANCE = 0.01
DEFAULT_DECIMAL_STYLE = "iso"


# ── sha256 helper (no dependency on load_contract) ────────────────


def _sha256_of(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


# ── Data-class ────────────────────────────────────────────────────


@dataclass
class TenantConfig:
    tenant_id: Optional[str]
    aliases: dict[str, dict[str, list[str]]]
    date_formats: list[str]
    decimal_style: str
    balance_tolerance: float
    severity_overrides: dict[str, str]
    natural_keys: dict[str, list[str]]
    config_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id":          self.tenant_id,
            "aliases":            self.aliases,
            "date_formats":       list(self.date_formats),
            "decimal_style":      self.decimal_style,
            "balance_tolerance":  self.balance_tolerance,
            "severity_overrides": self.severity_overrides,
            "natural_keys":       self.natural_keys,
            "config_hash":        self.config_hash,
        }


# ── Constructors ──────────────────────────────────────────────────


def empty_tenant_config(tenant_id: Optional[str] = None) -> TenantConfig:
    cfg = TenantConfig(
        tenant_id=tenant_id,
        aliases={},
        date_formats=[],
        decimal_style=DEFAULT_DECIMAL_STYLE,
        balance_tolerance=DEFAULT_BALANCE_TOLERANCE,
        severity_overrides={},
        natural_keys={},
    )
    cfg.config_hash = _compute_config_hash(cfg)
    return cfg


def load_tenant_config(path: str | Path) -> TenantConfig:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"tenant config not found: {p}")

    suffix = p.suffix.lower()
    if suffix == ".json":
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
    elif suffix in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "loading a YAML tenant config requires PyYAML; "
                "install pyyaml or use a JSON config instead"
            ) from exc
        with p.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    else:
        raise ValueError(f"unsupported tenant config extension: {suffix!r}")

    if not isinstance(data, Mapping):
        raise ValueError(
            f"tenant config root must be an object/mapping; got {type(data).__name__}"
        )

    cfg = TenantConfig(
        tenant_id=_optional_str(data.get("tenant_id")),
        aliases=_normalise_aliases(data.get("aliases", {})),
        date_formats=[str(x) for x in data.get("date_formats", []) if x is not None],
        decimal_style=str(data.get("decimal_style", DEFAULT_DECIMAL_STYLE)),
        balance_tolerance=float(data.get("balance_tolerance", DEFAULT_BALANCE_TOLERANCE)),
        severity_overrides={
            str(k): str(v)
            for k, v in (data.get("severity_overrides", {}) or {}).items()
        },
        natural_keys=_normalise_natural_keys(data.get("natural_keys", {})),
    )
    cfg.config_hash = _compute_config_hash(cfg)
    return cfg


# ── Internal helpers ──────────────────────────────────────────────


def _optional_str(v: Any) -> Optional[str]:
    return None if v is None else str(v)


def _normalise_aliases(aliases: Any) -> dict[str, dict[str, list[str]]]:
    out: dict[str, dict[str, list[str]]] = {}
    if not isinstance(aliases, Mapping):
        return out
    for data_type, fields in aliases.items():
        if not isinstance(fields, Mapping):
            continue
        per_dt: dict[str, list[str]] = {}
        for canonical_field, alias_value in fields.items():
            if isinstance(alias_value, str):
                per_dt[str(canonical_field)] = [alias_value]
            elif isinstance(alias_value, Sequence):
                per_dt[str(canonical_field)] = [str(a) for a in alias_value]
        out[str(data_type)] = per_dt
    return out


def _normalise_natural_keys(nk: Any) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    if not isinstance(nk, Mapping):
        return out
    for data_type, fields in nk.items():
        if isinstance(fields, str):
            out[str(data_type)] = [fields]
        elif isinstance(fields, Sequence):
            out[str(data_type)] = [str(f) for f in fields]
    return out


def _compute_config_hash(cfg: TenantConfig) -> str:
    payload = {
        "tenant_id":          cfg.tenant_id,
        "aliases":            cfg.aliases,
        "date_formats":       list(cfg.date_formats),
        "decimal_style":      cfg.decimal_style,
        "balance_tolerance":  cfg.balance_tolerance,
        "severity_overrides": cfg.severity_overrides,
        "natural_keys":       cfg.natural_keys,
    }
    return _sha256_of(payload)
