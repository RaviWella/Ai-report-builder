"""HR dbt runner — per-tenant warehouse database + schema vars."""
from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

from app.core.warehouse import connection_params, dbt_vars

logger = logging.getLogger("hr_etl.dbt")

DBT_PROJECT_DIR = Path(__file__).parents[3] / "dbt_project" / "hr_mart"

# Top-level folders created under dbt_packages/ by packages.yml (not transitive deps).
REQUIRED_DBT_PACKAGES = (
    "dbt_utils",
    "dbt_expectations",
    "codegen",
    "dbt_artifacts",
)


def resolve_dbt_executable() -> str:
    """Locate dbt CLI (PATH or same Python install Scripts/)."""
    found = shutil.which("dbt")
    if found:
        return found
    scripts_dbt = Path(sys.executable).resolve().parent / "dbt.exe"
    if scripts_dbt.is_file():
        return str(scripts_dbt)
    raise FileNotFoundError(
        "dbt not found. Install: pip install dbt-core dbt-postgres"
    )


class HrDbtRunner:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    @staticmethod
    def _deps_installed() -> bool:
        packages_dir = DBT_PROJECT_DIR / "dbt_packages"
        if not packages_dir.is_dir():
            return False
        return all((packages_dir / name).is_dir() for name in REQUIRED_DBT_PACKAGES)

    def _run_dbt_deps(self) -> dict[str, Any]:
        """Install packages.yml deps (no warehouse profile required)."""
        dbt_bin = resolve_dbt_executable()
        cmd = [
            dbt_bin,
            "deps",
            "--project-dir",
            str(DBT_PROJECT_DIR),
            "--no-use-colors",
        ]
        logger.info("dbt cmd: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300
            )
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout[-3000:] if result.stdout else "",
                "stderr": result.stderr[-2000:] if result.stderr else "",
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "exception": "dbt deps timeout (300s)"}
        except FileNotFoundError as exc:
            logger.error("dbt not found: %s", exc)
            return {"success": False, "skipped": True, "error": str(exc)}

    def ensure_deps(self) -> dict[str, Any]:
        """Install packages.yml deps when dbt_packages is missing (gitignored)."""
        if self._deps_installed():
            return {"success": True, "skipped": True}
        logger.info("dbt_packages incomplete — running dbt deps")
        summary = self._run_dbt_deps()
        require_dbt_success(summary)
        if not self._deps_installed():
            raise RuntimeError(
                "dbt deps finished but required packages are still missing in "
                f"{DBT_PROJECT_DIR / 'dbt_packages'}"
            )
        return summary

    def _build_profiles(self) -> str:
        params = connection_params(self.tenant_id)
        profiles = {
            "hr_mart": {
                "target": self.tenant_id,
                "outputs": {
                    self.tenant_id: {
                        "type": "postgres",
                        "host": params["host"],
                        "port": int(params["port"]),
                        "user": params["user"],
                        "password": params["password"],
                        "dbname": params["database"],
                        "schema": "public",
                        "threads": 4,
                    }
                },
            }
        }
        tmp = tempfile.mkdtemp()
        profiles_path = os.path.join(tmp, "profiles.yml")
        with open(profiles_path, "w", encoding="utf-8") as f:
            yaml.dump(profiles, f)
        return tmp

    def _run_dbt(
        self, command: list[str], *, timeout_seconds: int = 600
    ) -> dict[str, Any]:
        profiles_dir = self._build_profiles()
        vars_payload = json.dumps(dbt_vars(self.tenant_id))
        dbt_bin = resolve_dbt_executable()
        cmd = [
            dbt_bin,
            *command,
            "--project-dir",
            str(DBT_PROJECT_DIR),
            "--profiles-dir",
            profiles_dir,
            "--target",
            self.tenant_id,
            "--vars",
            vars_payload,
            "--no-use-colors",
        ]
        logger.info("dbt cmd: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_seconds
            )
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout[-3000:] if result.stdout else "",
                "stderr": result.stderr[-2000:] if result.stderr else "",
                "total": 0,
                "counts": {},
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "exception": f"dbt timeout ({timeout_seconds}s)",
            }
        except FileNotFoundError as exc:
            logger.error("dbt not found: %s", exc)
            return {"success": False, "skipped": True, "error": str(exc), "total": 0, "counts": {}}

    def snapshot(self) -> dict[str, Any]:
        self.ensure_deps()
        return self._run_dbt(["snapshot"])

    def run(self) -> dict[str, Any]:
        self.ensure_deps()
        # `dbt build` orders seed → staging/int → snapshots → marts correctly.
        # Tests run separately via test(); one bad test must not block mart load.
        return self._run_dbt(
            ["build", "--exclude", "resource_type:test", "tag:custom_reports"],
        )

    def test(self) -> dict[str, Any]:
        self.ensure_deps()
        return self._run_dbt(["test"])


def _extract_dbt_failure_message(summary: dict[str, Any]) -> str:
    """Prefer dbt's error block over progress tail (stdout is often truncated)."""
    blob = "\n".join(
        part
        for part in (
            summary.get("stderr"),
            summary.get("stdout"),
            summary.get("exception"),
            summary.get("error"),
        )
        if part
    )
    if not blob:
        return "dbt failed"

    markers = (
        "Database Error in model",
        "Compilation Error in model",
        "Runtime Error in model",
        "Unhandled error while executing",
        "Failure in model",
    )
    lines = blob.splitlines()
    for i, line in enumerate(lines):
        if any(m in line for m in markers):
            chunk = [line.strip()]
            for follow in lines[i + 1 : i + 12]:
                s = follow.strip()
                if not s:
                    if len(chunk) > 1:
                        break
                    continue
                if s.startswith("05:") and " of " in s and " START " in s:
                    break
                chunk.append(s)
            return "\n".join(chunk)

    return blob[-2000:] if len(blob) > 2000 else blob


def require_dbt_success(summary: dict[str, Any]) -> None:
    """Raise if dbt did not build marts (missing CLI or non-zero exit)."""
    if summary.get("skipped"):
        raise RuntimeError(
            "dbt is not installed. Install with: pip install dbt-core dbt-postgres"
        )
    if not summary.get("success"):
        detail = _extract_dbt_failure_message(summary)
        raise RuntimeError(f"dbt transform failed: {str(detail)[:2000]}")
