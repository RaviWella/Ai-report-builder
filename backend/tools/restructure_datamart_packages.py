"""
One-time datamart package restructure: move modules into subpackages and fix imports.

Run from backend/:  python tools/restructure_datamart_packages.py
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DM = BACKEND / "app" / "services" / "ai_services" / "datamart"

MOVES: dict[str, str] = {
    "sql_aliases.py": "sql",
    "sql_answer_adequacy.py": "sql",
    "sql_binding.py": "sql",
    "sql_binding_rewrite.py": "sql",
    "sql_column_allowlist.py": "sql",
    "sql_exec_guard.py": "sql",
    "sql_exec_repairs.py": "sql",
    "sql_faithfulness.py": "sql",
    "sql_fast_path.py": "sql",
    "sql_generation.py": "sql",
    "sql_generation_critic.py": "sql",
    "sql_null_policy.py": "sql",
    "sql_recovery.py": "sql",
    "sql_refs.py": "sql",
    "sql_repairs.py": "sql",
    "sql_retry.py": "sql",
    "sql_safety.py": "sql",
    "sql_table_normalize.py": "sql",
    "llm_client.py": "llm",
    "llm_settings.py": "llm",
    "llm_response.py": "llm",
    "llm_context_log.py": "llm",
    "prompt_budget.py": "llm",
    "chat_prompts.py": "prompts",
    "simple_prompts.py": "prompts",
    "simple_context.py": "prompts",
    "template_prompts.py": "prompts",
    "grounded_schema_prompt.py": "prompts",
    "simple_history.py": "prompts",
    "scenario_pipeline.py": "scenario",
    "scenario_history.py": "scenario",
    "scenario_scope.py": "scenario",
    "extra_blocks.py": "scenario",
    "block_merge.py": "scenario",
    "semantic_layer.py": "semantic",
    "semantic_catalog_paths.py": "semantic",
    "semantic_catalog_sync.py": "semantic",
    "join_hints.py": "semantic",
    "datahub.py": "semantic",
    "datahub_scope.py": "semantic",
    "grounding_prune.py": "semantic",
    "column_projection.py": "semantic",
    "column_value_peek.py": "semantic",
    "dimension_enrich.py": "semantic",
    "catalog_report_sql.py": "domain_sql",
    "workforce_sql_template.py": "domain_sql",
    "leave_report_sql.py": "domain_sql",
    "payroll_report_sql.py": "domain_sql",
    "employee_list_sql.py": "domain_sql",
    "employee_bank_detail_sql.py": "domain_sql",
    "employee_shift_sql.py": "domain_sql",
    "recruitment_pipeline_sql.py": "domain_sql",
    "recruitment_hire_proxy_sql.py": "domain_sql",
    "probation_report_sql.py": "domain_sql",
    "report_spec.py": "domain_sql",
    "report_sql_router.py": "domain_sql",
    "metric_templates.py": "domain_sql",
    "validation_models.py": "validation",
    "validation_context.py": "validation",
    "validation_runner.py": "validation",
    "pipeline_validation.py": "validation",
    "report_spec_validate.py": "validation",
    "trust_scorer.py": "validation",
    "retrieval_validator.py": "validation",
    "retrieval_relevance.py": "validation",
    "adequacy_resolve.py": "validation",
    "post_processor.py": "postprocess",
    "post_process_validate.py": "postprocess",
    "narrative_insights.py": "postprocess",
    "is_current_policy.py": "postprocess",
    "session_service.py": "workspace",
    "workspace_service.py": "workspace",
    "workspace_scope.py": "workspace",
    "runtime_context.py": "workspace",
    "auth_context.py": "workspace",
    "tenant_dependency.py": "workspace",
    "observability.py": "workspace",
    "chat_engine.py": "orchestration",
    "chat_run_context.py": "orchestration",
    "template_pipeline.py": "orchestration",
    "intent_router.py": "orchestration",
    "modify_mode.py": "orchestration",
    "clarification_flow.py": "orchestration",
    "clarification_messages.py": "orchestration",
    "refinement_guard.py": "orchestration",
    "template_sql_guard.py": "orchestration",
    "schema_linker.py": "orchestration",
}

FROM_IMPORT_RE = re.compile(
    r"^(\s*)from ((?:\.*)(?:[a-zA-Z0-9_]+\.)*[a-zA-Z0-9_]+) import ",
    re.MULTILINE,
)


def _stem(name: str) -> str:
    return name.replace(".py", "")


def _build_location_map() -> dict[str, str]:
    loc: dict[str, str] = {}
    for path in DM.rglob("*.py"):
        if path.name == "__init__.py":
            continue
        rel = path.relative_to(DM)
        parts = list(rel.parts)
        if len(parts) == 1:
            loc[_stem(parts[0])] = _stem(parts[0])
        else:
            loc[_stem(parts[-1])] = ".".join(_stem(p) for p in parts)
    return loc


def _make_relative(from_file: Path, target_dotted: str) -> str:
    from_parts = (
        ()
        if from_file.parent == DM
        else tuple(from_file.parent.relative_to(DM).parts)
    )
    to_parts = tuple(target_dotted.split("."))
    i = 0
    while (
        i < len(from_parts)
        and i < len(to_parts) - 1
        and from_parts[i] == to_parts[i]
    ):
        i += 1
    ups = len(from_parts) - i
    prefix = "." * (ups + 1)
    remainder = ".".join(to_parts[i:])
    return f"{prefix}{remainder}" if remainder else prefix


def move_files() -> None:
    for filename, pkg in MOVES.items():
        src = DM / filename
        if not src.exists():
            continue
        dest_dir = DM / pkg
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / filename
        if dest.exists():
            continue
        shutil.move(str(src), str(dest))

    sem = DM / "semantic"
    sem.mkdir(parents=True, exist_ok=True)
    for name in ("semantic_catalog.yaml",):
        src = DM / name
        if src.exists() and not (sem / name).exists():
            shutil.move(str(src), str(sem / name))
    cat_src = DM / "semantic_catalogs"
    if cat_src.exists() and not (sem / "semantic_catalogs").exists():
        shutil.move(str(cat_src), str(sem / "semantic_catalogs"))


def fix_imports() -> None:
    loc = _build_location_map()
    moved_stems = {_stem(k) for k in MOVES}

    for pyf in BACKEND.rglob("*.py"):
        if "restructure_datamart_packages" in pyf.name:
            continue
        text = pyf.read_text(encoding="utf-8")
        original = text

        for stem in sorted(moved_stems, key=len, reverse=True):
            new_abs = f"app.services.ai_services.datamart.{loc[stem]}"
            old_abs = f"app.services.ai_services.datamart.{stem}"
            if old_abs != new_abs:
                text = text.replace(old_abs, new_abs)

        def _fix_from(m: re.Match) -> str:
            indent, rel = m.group(1), m.group(2)
            path_part = rel.lstrip(".")
            if not path_part:
                return m.group(0)
            parts = path_part.split(".")
            stem = parts[-1]
            if stem not in loc:
                return m.group(0)
            target = loc[stem]
            if pyf.is_relative_to(DM):
                new_rel = _make_relative(pyf, target)
            else:
                return m.group(0)
            if new_rel == rel.lstrip(".") and rel.startswith("."):
                return m.group(0)
            if new_rel == path_part and f".{path_part}" == rel:
                return m.group(0)
            return f"{indent}from {new_rel} import "

        text = FROM_IMPORT_RE.sub(_fix_from, text)

        if text != original:
            pyf.write_text(text, encoding="utf-8")


def write_package_inits() -> None:
    readmes = {
        "sql": "SQL generation, binding, execution guards, repairs, and recovery.",
        "llm": "LLM client, settings, response parsing, and prompt budget.",
        "prompts": "System/user prompts and schema context for chat and templates.",
        "scenario": "Multi-scenario reports, extra result blocks, and scope.",
        "semantic": "Semantic catalog, DataHub, join hints, and column peeks.",
        "domain_sql": "Domain-specific SQL templates and report specs (Tier A).",
        "validation": "Report validation, trust scoring, and retrieval gates.",
        "postprocess": "Post-processing transforms and row policies.",
        "workspace": "Sessions, templates, tenant runtime, and auth context.",
        "orchestration": "Chat engine, modify/scenario mode, clarification, templates.",
    }
    for pkg, desc in readmes.items():
        d = DM / pkg
        d.mkdir(parents=True, exist_ok=True)
        init = d / "__init__.py"
        if not init.exists():
            init.write_text(f'"""Datamart {pkg}: {desc}"""\n', encoding="utf-8")
        readme = d / "README.md"
        readme.write_text(f"# datamart/{pkg}\n\n{desc}\n", encoding="utf-8")


def write_root_readme() -> None:
    readme = DM / "README.md"
    readme.write_text(
        """# Datamart AI agent

## Layout

| Path | Purpose |
|------|---------|
| `agent.py`, `chat_pipeline.py` | Public entry points |
| `models.py`, `config.py`, `settings.py` | Shared models and settings |
| `schema.py`, `schema_broker.py` | Warehouse introspection and grounding |
| `pipeline/` | Chat pipeline stages and `runner.py` orchestrator |
| `sql/` | SQL generation, binding, execution, recovery |
| `llm/` | LLM client and response parsing |
| `prompts/` | Prompts and context assembly |
| `scenario/` | Add-scenario and extra result blocks |
| `semantic/` | Catalog, DataHub, join hints |
| `domain_sql/` | Domain SQL templates (Tier A) |
| `validation/` | Validation and trust |
| `postprocess/` | Post-process transforms |
| `workspace/` | Sessions, templates, tenant runtime |
| `orchestration/` | Modify mode, clarification, template pipeline |
""",
        encoding="utf-8",
    )


def main() -> None:
    move_files()
    fix_imports()
    write_package_inits()
    write_root_readme()
    print("Datamart restructure complete.")


if __name__ == "__main__":
    main()
