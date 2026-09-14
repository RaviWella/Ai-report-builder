"""Scope continue_last modifications to selected report scenarios."""
from __future__ import annotations

import json
from typing import Any, Callable, Optional

from ..models import DatamartResponse, DatamartResultBlock

PRIMARY_SCENARIO_ID = "primary"


def normalize_target_scenario_ids(
    raw: Optional[list[str]],
) -> Optional[set[str]]:
    if not raw:
        return None
    out = {str(s).strip() for s in raw if s and str(s).strip()}
    return out or None


def format_target_scenario_addon(
    target_ids: set[str],
    *,
    primary_sql: Optional[str],
    primary_post_process: Optional[list[dict]],
    extra_blocks: Optional[list[dict]],
) -> str:
    """User-prompt addon: LLM must only change the selected scenario(s)."""
    labels: list[str] = []
    if PRIMARY_SCENARIO_ID in target_ids:
        labels.append("Primary scenario (top-level SQL + POST_PROCESS)")
    for blk in extra_blocks or []:
        if not isinstance(blk, dict):
            continue
        bid = str(blk.get("block_id") or "").strip()
        if bid and bid in target_ids:
            title = (blk.get("title") or "Additional scenario").strip()
            labels.append(f'Extra scenario "{title}" (block_id={bid})')

    lines = [
        "\n\n## Intent: modify selected scenario(s) only",
        "The user explicitly chose to apply this request **only** to:",
    ]
    for label in labels:
        lines.append(f"- {label}")
    lines.extend(
        [
            "",
            "**Mandatory rules:**",
            "- Do **not** change SQL, POST_PROCESS, or ADDITIONAL_RESULT_BLOCKS for any scenario "
            "that is **not** listed above.",
            "- Other scenarios in this report must stay **byte-for-byte identical** to the anchors below.",
        ]
    )

    only_extras = PRIMARY_SCENARIO_ID not in target_ids
    only_primary = target_ids == {PRIMARY_SCENARIO_ID}

    if only_extras:
        lines.extend(
            [
                "- **Do not** output a top-level SQL block for the primary scenario (omit ```sql``` "
                "or repeat the primary SQL unchanged if the format requires a block).",
                "- Put all SQL changes in **ADDITIONAL_RESULT_BLOCKS**, reusing the **same block_id** "
                "for each selected extra scenario.",
            ]
        )
    elif only_primary:
        lines.append(
            "- Change only the **top-level SQL** and **POST_PROCESS**; "
            "**omit** ADDITIONAL_RESULT_BLOCKS entirely."
        )
    else:
        lines.append(
            "- Use top-level SQL + POST_PROCESS for the primary scenario when it is selected; "
            "use ADDITIONAL_RESULT_BLOCKS with existing **block_id** values for selected extras."
        )

    if PRIMARY_SCENARIO_ID in target_ids and primary_sql and str(primary_sql).strip():
        lines.extend(
            [
                "",
                "### Primary scenario anchor (edit minimally)",
                "```sql",
                str(primary_sql).strip(),
                "```",
            ]
        )
        if primary_post_process:
            pp_json = json.dumps(primary_post_process, indent=2)
            lines.extend(
                [
                    "[POST_PROCESS for primary — update only if the user asked to change summaries/labels]",
                    f"```json\n{pp_json}\n```",
                ]
            )

    for blk in extra_blocks or []:
        if not isinstance(blk, dict):
            continue
        bid = str(blk.get("block_id") or "").strip()
        if bid not in target_ids:
            continue
        title = (blk.get("title") or "Additional scenario").strip()
        sql_b = blk.get("sql_script") or blk.get("sql") or ""
        lines.extend(
            [
                "",
                f'### Extra scenario anchor: {title} (block_id={bid})',
                "```sql",
                str(sql_b).strip(),
                "```",
            ]
        )
        pp_b = blk.get("post_process_config")
        if pp_b:
            lines.extend(
                [
                    f"[POST_PROCESS for block_id={bid}]",
                    f"```json\n{json.dumps(pp_b, indent=2)}\n```",
                ]
            )

    return "\n".join(lines)


def _restore_prior_extra_block(
    prior_blk: dict,
    execute_fn: Callable[[str, Optional[list]], Any],
) -> DatamartResultBlock:
    """Keep untouched scenario data (cached rows or re-execute stored SQL)."""
    bid = str(prior_blk.get("block_id") or "")
    title = prior_blk.get("title")
    sql_val = prior_blk.get("sql_script") or prior_blk.get("sql")
    pp = (
        prior_blk.get("post_process_config")
        if isinstance(prior_blk.get("post_process_config"), list)
        else None
    )
    cols = prior_blk.get("columns")
    rows = prior_blk.get("rows")
    if isinstance(cols, list) and isinstance(rows, list) and len(rows) > 0:
        rc = prior_blk.get("row_count")
        return DatamartResultBlock(
            block_id=bid,
            title=title,
            sql=str(sql_val) if sql_val else None,
            post_process_config=pp,
            columns=list(cols),
            rows=rows,
            row_count=int(rc) if rc is not None else len(rows),
            validation=prior_blk.get("validation")
            if isinstance(prior_blk.get("validation"), dict)
            else None,
        )
    if sql_val and str(sql_val).strip():
        exec_resp = execute_fn(str(sql_val).strip(), pp)
        return DatamartResultBlock(
            block_id=bid,
            title=title,
            sql=str(sql_val).strip(),
            post_process_config=pp,
            columns=getattr(exec_resp, "columns", None),
            rows=getattr(exec_resp, "rows", None),
            row_count=getattr(exec_resp, "row_count", None) or 0,
            raw_columns=getattr(exec_resp, "raw_columns", None),
            raw_rows=getattr(exec_resp, "raw_rows", None),
            raw_row_count=getattr(exec_resp, "raw_row_count", None),
            error=getattr(exec_resp, "error", None),
        )
    return DatamartResultBlock(
        block_id=bid,
        title=title,
        sql=str(sql_val) if sql_val else None,
        post_process_config=pp,
        error="Prior scenario SQL missing",
    )


def apply_target_scope_to_result(
    result: DatamartResponse,
    *,
    targets: set[str],
    prior_sql: Optional[str],
    prior_post_process: Optional[list[dict]],
    prior_extra_blocks: Optional[list[dict]],
    execute_primary: Callable[[str, Optional[list]], Any],
) -> DatamartResponse:
    """
    After the LLM pipeline, restore untouched scenarios from the prior assistant turn.
    """
    if PRIMARY_SCENARIO_ID not in targets and prior_sql:
        result.sql = prior_sql
        result.post_process_config = prior_post_process
        exec_resp = execute_primary(prior_sql, prior_post_process)
        if getattr(exec_resp, "error", None) and not getattr(exec_resp, "columns", None):
            result.error = exec_resp.error
        else:
            result.columns = exec_resp.columns
            result.rows = exec_resp.rows
            result.row_count = exec_resp.row_count
            result.raw_columns = getattr(exec_resp, "raw_columns", None)
            result.raw_rows = getattr(exec_resp, "raw_rows", None)
            result.raw_row_count = getattr(exec_resp, "raw_row_count", None)
            if getattr(exec_resp, "error", None):
                result.error = exec_resp.error
            elif result.error and exec_resp.columns:
                result.error = None

    if prior_extra_blocks:
        prior_by_id = {
            str(b.get("block_id")): b
            for b in prior_extra_blocks
            if isinstance(b, dict) and b.get("block_id")
        }
        new_by_id = {b.block_id: b for b in (result.extra_result_blocks or [])}
        merged_extras: list[DatamartResultBlock] = []
        for bid, prior_blk in prior_by_id.items():
            if bid in targets and bid in new_by_id:
                merged_extras.append(new_by_id[bid])
            else:
                merged_extras.append(
                    _restore_prior_extra_block(prior_blk, execute_primary)
                )
        for bid, blk in new_by_id.items():
            if bid not in prior_by_id:
                merged_extras.append(blk)
        result.extra_result_blocks = merged_extras or None

    return result
