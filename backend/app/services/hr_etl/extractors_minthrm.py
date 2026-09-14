"""MintHRM extractors — LinHR / MintHRM tables; source SQL is MySQL or PostgreSQL aware.

SQL fragments are built via ``sql_dialect`` inside ``source_dialect()`` (set by the ETL runner).

Source tables: hr_empbasic, hr_employment, hr_empcontact, hr_leavetype,
hr_leaveapplication, HR_ATTEDANCE, hr_designation, branch, company_hierarchy,
VW_MINT_EMP_DEPARTMENT, processed_sal_basic_data, processed_sal_add_ded,
processed_sal_attendance, prl_variableadditions_forsal,
prl_variabledeductions_forsal, etc.

Enable via MYSQL_EXTRACTOR_PROFILE=minthrm in backend/.env
"""
from __future__ import annotations

from typing import Callable

from sqlalchemy.engine import Engine

import datetime

from app.services.hr_etl.sql_dialect import (
    qident,
    sql_cast_signed_int,
    sql_cast_text,
    sql_date_diff_inclusive,
    sql_hash_mod_int,
    sql_minute_diff,
    sql_month,
    sql_now,
    sql_payroll_run_code,
    sql_safe_date_case,
    sql_year,
    sql_substring_index,
    sql_time_to_seconds,
    sql_timestamp_from_date_and_time,
    sql_zero_date_null,
)
from app.services.hr_etl.extractors import (
    _bool,
    _date,
    _float,
    _int,
    _safe_date,
    _safe_datetime,
    _str,
    _stream_extract,
)
from app.services.hr_etl.source_mapping import SourceMapping, get_source_mapping


def _m() -> SourceMapping:
    return get_source_mapping()


def _employment_join_sql(m: SourceMapping, *, basic_alias: str = "b") -> str:
    emp_t = m.table("employment")
    e_id = m.physical_col("employment", "id")
    e_ref = m.physical_col("employment", "ref_emp_id")
    b_id = m.physical_col("emp_basic", "id")
    return f"""
    LEFT JOIN {emp_t} emp ON emp.{e_ref} = {basic_alias}.{b_id}
        AND emp.{e_id} = (
            SELECT MAX(e2.{e_id})
            FROM {emp_t} e2
            WHERE e2.{e_ref} = {basic_alias}.{b_id}
        )
    """


def extract_company_hierarchy_individual(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """Per-employee org chart node — parent_id is immediate superior (ref_emp_id)."""
    m = _m()
    chi = "chi"
    now = sql_now()
    sql = f"""
        SELECT
            {m.ref('company_hierarchy_individual', 'id', chi)}     AS id,
            {m.ref('company_hierarchy_individual', 'ref_emp_id', chi)}
                                                                   AS ref_emp_id,
            {m.ref('company_hierarchy_individual', 'parent_id', chi)}
                                                                   AS parent_id,
            {now}                                                  AS created_at,
            {now}                                                  AS updated_at
        FROM {m.table('company_hierarchy_individual')} {chi}
        WHERE {m.ref('company_hierarchy_individual', 'ref_emp_id', chi)} IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_company_hierarchy_individual", sql,
        [
            ("id", _int),
            ("ref_emp_id", _int),
            ("parent_id", _int),
            ("created_at", _safe_datetime),
            ("updated_at", _safe_datetime),
        ],
        incremental=False,
        pk_column="id",
    )


def extract_employees(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    m = _m()
    b, c, emp, et, des, gr, cat, le, br, vd = (
        "b", "c", "emp", "et", "des", "gr", "cat", "le", "br", "vd"
    )
    name_col = m.ref("emp_basic", "name", b)
    first_name = f"TRIM({sql_substring_index(name_col, ' ', 1)})"
    last_name = f"TRIM({sql_substring_index(name_col, ' ', -1)})"
    dept_fallback = sql_cast_signed_int(
        sql_hash_mod_int(
            f"COALESCE({m.ref('emp_department_view', 'department_name', vd)}, 'Unknown')"
        )
    )
    now = sql_now()
    sql = f"""
        SELECT
            {m.ref('emp_basic', 'id', b)}               AS id,
            {m.ref('emp_basic', 'employee_code', b)}    AS employee_code,
            {first_name}                                AS first_name,
            {last_name}                                 AS last_name,
            COALESCE(NULLIF({m.ref('emp_basic', 'full_name', b)}, ''),
                     {name_col})                        AS full_name,
            {m.ref('emp_basic', 'gender', b)}           AS gender,
            {m.ref('emp_basic', 'date_of_birth', b)}    AS date_of_birth,
            {m.ref('emp_basic', 'national_id', b)}      AS national_id,
            {m.ref('emp_contact', 'email', c)}          AS email,
            COALESCE({m.ref('emp_contact', 'mobile1', c)},
                     {m.ref('emp_contact', 'mobile2', c)}) AS phone,
            COALESCE(
                {m.ref('employment', 'section_id', emp)},
                {dept_fallback}
            )                                           AS department_id,
            {m.ref('employment', 'designation_id', emp)} AS designation_id,
            {m.ref('employment', 'branch_id', emp)}     AS branch_id,
            NULL                                        AS cost_center_id,
            COALESCE(LOWER({m.ref('emp_type', 'name', et)}), 'permanent')
                                                        AS employment_type,
            CASE
                WHEN LOWER({m.ref('emp_basic', 'status', b)}) = 'active' THEN 'active'
                WHEN LOWER({m.ref('emp_basic', 'status', b)}) IN ('resign', 'resigned')
                    THEN 'resigned'
                WHEN {m.ref('emp_basic', 'terminate_effectivedate', b)} IS NOT NULL
                    THEN 'terminated'
                ELSE LOWER(COALESCE({m.ref('emp_basic', 'status', b)}, 'active'))
            END                                         AS employment_status,
            {m.ref('employment', 'join_date', emp)}     AS date_joined,
            NULL                                        AS date_confirmed,
            {sql_zero_date_null(m.ref('emp_basic', 'last_resigned_date', b))}
                                                        AS date_resigned,
            {sql_safe_date_case(m.ref('emp_basic', 'terminate_effectivedate', b))}
                                                        AS date_terminated,
            {m.ref('employment', 'superior_id', emp)}   AS reporting_to,
            {m.ref('emp_basic', 'legal_entity_id', b)}    AS legal_entity_id,
            COALESCE(
                NULLIF(TRIM({m.ref('legal_entity', 'title', le)}), ''),
                NULLIF(TRIM({m.ref('emp_basic', 'legal_entity_ref', b)}), '')
            )                                           AS legal_entity_name,
            NULLIF(TRIM({m.ref('legal_entity', 'code', le)}), '')
                                                        AS legal_entity_code,
            NULLIF(TRIM({m.ref('designation', 'title', des)}), '')
                                                        AS designation_name,
            NULLIF(TRIM({m.ref('designation', 'department_ref', des)}), '')
                                                        AS designation_department,
            NULLIF(TRIM({m.ref('grade', 'title', gr)}), '')
                                                        AS grade_name,
            NULLIF(TRIM({m.ref('emp_category', 'title', cat)}), '')
                                                        AS employee_category,
            {sql_cast_text(m.ref('emp_category', 'id', cat))}
                                                        AS employee_category_code,
            NULLIF(TRIM({m.ref('branch', 'name', br)}), '')
                                                        AS location_name,
            NULLIF({m.ref('emp_basic', 'basic_salary', b)}, 0)
                                                        AS basic_salary,
            NULLIF(TRIM({m.ref('emp_basic', 'epf_no', b)}), '')
                                                        AS epf_no,
            COALESCE({m.ref('emp_basic', 'modified_date', b)},
                     {m.ref('emp_basic', 'create_date', b)}, {now})
                                                        AS created_at,
            COALESCE({m.ref('emp_basic', 'modified_date', b)},
                     {m.ref('emp_basic', 'create_date', b)}, {now})
                                                        AS updated_at
        FROM {m.table('emp_basic')} {b}
        LEFT JOIN {m.table('emp_contact')} {c}
            ON {m.ref('emp_contact', 'ref_emp_id', c)} = {m.ref('emp_basic', 'id', b)}
        {_employment_join_sql(m, basic_alias=b)}
        LEFT JOIN {m.table('emp_type')} {et}
            ON {m.ref('emp_type', 'id', et)} = {m.ref('employment', 'employment_type_id', emp)}
        LEFT JOIN {m.table('designation')} {des}
            ON {m.ref('designation', 'id', des)} = {m.ref('employment', 'designation_id', emp)}
        LEFT JOIN {m.table('grade')} {gr}
            ON {m.ref('grade', 'id', gr)} = {m.ref('employment', 'grade_id', emp)}
        LEFT JOIN {m.table('emp_category')} {cat}
            ON {m.ref('emp_category', 'id', cat)} = {m.ref('employment', 'category_id', emp)}
        LEFT JOIN {m.table('legal_entity')} {le}
            ON {m.ref('legal_entity', 'id', le)} = {m.ref('emp_basic', 'legal_entity_id', b)}
        LEFT JOIN {m.table('branch')} {br}
            ON {m.ref('branch', 'id', br)} = {m.ref('employment', 'branch_id', emp)}
        LEFT JOIN {m.table('emp_department_view')} {vd}
            ON {m.ref('emp_department_view', 'emp_id', vd)} = {m.ref('emp_basic', 'id', b)}
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_employees", sql,
        [
            ("id", _int), ("employee_code", _str), ("first_name", _str),
            ("last_name", _str), ("full_name", _str), ("gender", _str),
            ("date_of_birth", _safe_date), ("national_id", _str), ("email", _str),
            ("phone", _str), ("department_id", _int), ("designation_id", _int),
            ("branch_id", _int), ("cost_center_id", _int),
            ("employment_type", _str), ("employment_status", _str),
            ("date_joined", _safe_date), ("date_confirmed", _safe_date),
            ("date_resigned", _safe_date), ("date_terminated", _safe_date),
            ("reporting_to", _int),
            ("legal_entity_id", _int), ("legal_entity_name", _str),
            ("legal_entity_code", _str), ("designation_name", _str),
            ("designation_department", _str), ("grade_name", _str),
            ("employee_category", _str), ("employee_category_code", _str),
            ("location_name", _str), ("basic_salary", _float),
            ("epf_no", _str),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_departments(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """Prefer company_hierarchy; fall back to VW_MINT_EMP_DEPARTMENT names."""
    now = sql_now()
    dept_hash_id = sql_cast_signed_int(sql_hash_mod_int("Department"))
    sql = f"""
        SELECT
            id,
            code,
            name,
            parent_id,
            head_employee_id,
            is_active,
            created_at,
            updated_at
        FROM (
            SELECT
                ch.id                                       AS id,
                COALESCE(NULLIF(ch.hierarchy_section_code, ''), {sql_cast_text('ch.id')})
                                                            AS code,
                ch.hierarchy_section_name                   AS name,
                ch.parent_id                                AS parent_id,
                ch.ref_leader_id                            AS head_employee_id,
                1                                           AS is_active,
                {now}                                       AS created_at,
                {now}                                       AS updated_at
            FROM company_hierarchy ch
            WHERE ch.hierarchy_section_name IS NOT NULL
              AND TRIM(ch.hierarchy_section_name) != ''
            UNION ALL
            SELECT
                {dept_hash_id}                              AS id,
                LEFT(Department, 64)                        AS code,
                Department                                  AS name,
                NULL                                        AS parent_id,
                NULL                                        AS head_employee_id,
                1                                           AS is_active,
                {now}                                       AS created_at,
                {now}                                       AS updated_at
            FROM (
                SELECT DISTINCT Department
                FROM VW_MINT_EMP_DEPARTMENT
                WHERE Department IS NOT NULL AND TRIM(Department) != ''
            ) vd
            WHERE NOT EXISTS (SELECT 1 FROM company_hierarchy LIMIT 1)
            UNION ALL
            SELECT 0, 'UNK', 'Unknown', NULL, NULL, 1, {now}, {now}
            WHERE NOT EXISTS (SELECT 1 FROM company_hierarchy LIMIT 1)
              AND NOT EXISTS (
                SELECT 1 FROM VW_MINT_EMP_DEPARTMENT
                WHERE Department IS NOT NULL AND TRIM(Department) != ''
              )
        ) dept_src
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_departments", sql,
        [
            ("id", _int), ("code", _str), ("name", _str),
            ("parent_id", _int), ("head_employee_id", _int),
            ("is_active", _bool), ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=False,
        pk_column="id",
    )


def extract_designations(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    sql = f"""
        SELECT
            desig_id        AS id,
            {sql_cast_text('desig_id')} AS code,
            designation     AS title,
            NULL            AS grade,
            NULL            AS department_id,
            1               AS is_active,
            created_date    AS created_at,
            updated_date    AS updated_at
        FROM hr_designation
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_designations", sql,
        [
            ("id", _int), ("code", _str), ("title", _str), ("grade", _str),
            ("department_id", _int), ("is_active", _bool),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_branches(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    now = sql_now()
    sql = f"""
        SELECT
            br_id           AS id,
            {sql_cast_text('br_id')} AS code,
            br_name         AS name,
            NULL            AS region,
            NULL            AS country,
            CASE
                WHEN br_active IS NULL OR LOWER(TRIM(br_active)) IN ('1', 'yes', 'active', 'y')
                THEN 1 ELSE 0
            END             AS is_active,
            {now}           AS created_at,
            {now}           AS updated_at
        FROM branch
        WHERE br_id IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_branches", sql,
        [
            ("id", _int), ("code", _str), ("name", _str),
            ("region", _str), ("country", _str), ("is_active", _bool),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col=None,
    )


def extract_attendance(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    m = _m()
    att_t = m.table("attendance")
    c_emp = m.physical_col("attendance", "emp_id")
    c_date = qident(m.physical_col("attendance", "date"))
    c_pin = m.physical_col("attendance", "punch_in")
    c_pout = m.physical_col("attendance", "punch_out")
    c_work = m.physical_col("attendance", "work_minutes")
    c_shift = m.physical_col("attendance", "shift_minutes")
    c_shift_in = m.physical_col("attendance", "shift_intime")
    c_in = m.physical_col("attendance", "intime")
    c_shift_id = m.physical_col("attendance", "shift_id")
    ts_in = sql_timestamp_from_date_and_time(c_date, c_pin)
    ts_out = sql_timestamp_from_date_and_time(c_date, c_pout)
    late_mins = sql_minute_diff(c_shift_in, c_in)
    sql = f"""
        SELECT
            id,
            {c_emp}                                     AS employee_id,
            {c_date}                                    AS attendance_date,
            check_in,
            check_out,
            status,
            late_minutes,
            early_leave_minutes,
            overtime_minutes,
            work_hours,
            {c_shift_id}                                AS shift_id,
            {c_date}                                    AS created_at,
            {c_date}                                    AS updated_at
        FROM (
            SELECT
                ROW_NUMBER() OVER (
                    ORDER BY {c_emp}, {c_date}, {c_shift_id}, {c_pin}, {c_pout}
                )                                       AS id,
                {c_emp},
                {c_date},
                CASE
                    WHEN {c_pin} IS NOT NULL AND {c_date} IS NOT NULL
                    THEN {ts_in}
                    ELSE NULL
                END                                     AS check_in,
                CASE
                    WHEN {c_pout} IS NOT NULL AND {c_date} IS NOT NULL
                    THEN {ts_out}
                    ELSE NULL
                END                                     AS check_out,
                CASE
                    WHEN COALESCE({c_work}, 0) > 0 THEN 'present'
                    ELSE 'absent'
                END                                     AS status,
                {late_mins}                             AS late_minutes,
                0                                       AS early_leave_minutes,
                GREATEST(
                    COALESCE({c_work}, 0) - COALESCE({c_shift}, 0), 0
                )                                       AS overtime_minutes,
                ROUND(COALESCE({c_work}, 0) / 60.0, 2) AS work_hours,
                {c_shift_id},
                {c_pin},
                {c_pout}
            FROM {att_t}
            WHERE {c_emp} IS NOT NULL AND {c_date} IS NOT NULL
        ) att
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_attendance", sql,
        [
            ("id", _int), ("employee_id", _int),
            ("attendance_date", _safe_date), ("check_in", None), ("check_out", None),
            ("status", _str), ("late_minutes", _int), ("early_leave_minutes", _int),
            ("overtime_minutes", _int), ("work_hours", _float), ("shift_id", _int),
            ("created_at", None), ("updated_at", None),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_lifecycle(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """hr_lifecycle (+ position lookup) → stg_lifecycle."""
    sql = f"""
        SELECT
            l.lifecycle_id                              AS id,
            l.ref_emp_id                                AS employee_id,
            l.lifecycle_position,
            p.position_name,
            l.effective_date,
            NULLIF(TRIM(l.previous_designation), '')      AS previous_designation,
            NULLIF(TRIM(l.ref_desig), '')                 AS new_designation,
            NULLIF(TRIM(l.previous_grade), '')              AS previous_grade,
            NULLIF(TRIM(l.ref_grade), '')                 AS new_grade,
            NULLIF(TRIM(l.previous_location), '')         AS previous_location,
            NULLIF(TRIM(l.ref_location), '')              AS new_location,
            NULLIF(TRIM(l.change_ref_legal_entity), '')   AS new_legal_entity,
            NULLIF(TRIM(l.company_section), '')           AS new_company_section,
            NULLIF(TRIM(l.section), '')                   AS new_section,
            NULLIF(TRIM(l.previous_section), '')          AS previous_section,
            NULLIF(l.basicsalary, 0)                      AS new_salary,
            NULLIF(l.previous_basicsalary, 0)             AS previous_salary,
            NULLIF(TRIM(l.lifecycle_comment), '')         AS reason,
            COALESCE(l.modified_by, l.update_emp_id, l.create_by)
                                                        AS triggered_by_emp_id,
            l.approval_date,
            l.approved_date_time,
            {sql_safe_date_case('l.resignation_approved_date')}
                                                        AS resignation_approved_date,
            {sql_safe_date_case('l.last_working_date')}
                                                        AS last_working_date,
            l.parent_ref_lifecycle_id                   AS parent_lifecycle_id,
            l.approval_status,
            l.create_date                               AS created_at,
            COALESCE(
                l.modified_date,
                l.update_date,
                l.approval_date,
                l.approved_date_time,
                l.create_date
            )                                           AS updated_at
        FROM hr_lifecycle l
        LEFT JOIN hr_lifecycle_position p
            ON p.position_id = l.lifecycle_position
        WHERE l.ref_emp_id IS NOT NULL
          AND l.effective_date IS NOT NULL
          AND l.effective_date >= '1900-01-01'
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_lifecycle", sql,
        [
            ("id", _int), ("employee_id", _int),
            ("lifecycle_position", _int), ("position_name", _str),
            ("effective_date", _safe_datetime),
            ("previous_designation", _str), ("new_designation", _str),
            ("previous_grade", _str), ("new_grade", _str),
            ("previous_location", _str), ("new_location", _str),
            ("new_legal_entity", _str), ("new_company_section", _str),
            ("new_section", _str), ("previous_section", _str),
            ("new_salary", _float), ("previous_salary", _float),
            ("reason", _str), ("triggered_by_emp_id", _int),
            ("approval_date", _safe_datetime),
            ("approved_date_time", _safe_datetime),
            ("resignation_approved_date", _safe_date),
            ("last_working_date", _safe_date),
            ("parent_lifecycle_id", _int), ("approval_status", _int),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_leave_types(
    source: Engine, pg: Engine, tenant_id: str
) -> int:
    now = sql_now()
    sql = f"""
        SELECT
            lvtype_id       AS id,
            COALESCE(NULLIF(lvtype_code, ''), {sql_cast_text('lvtype_id')}) AS code,
            lvtype_name     AS name,
            CASE WHEN COALESCE(lvtype_is_nopay, 0) = 1 THEN 0 ELSE 1 END AS is_paid,
            NULL            AS max_days_per_year,
            COALESCE(lvtype_carryforward_leave_status, 0) AS carry_forward,
            COALESCE(lvtype_need_cover, 0) AS requires_coverup,
            COALESCE(lvtype_attachment, 0) AS allow_attachment,
            COALESCE(lvtype_attachment_mandatory, 0) AS attachment_mandatory,
            CASE
                WHEN COALESCE(lvtype_approve_superior, 0) = 1
                  OR COALESCE(lvtype_approval_level, 0) > 0
                THEN 1 ELSE 0
            END             AS requires_approval,
            CASE WHEN COALESCE(lvtype_halfday_grace_mins, 0) > 0 THEN 1 ELSE 0 END
                            AS allow_half_day,
            COALESCE(lvtype_is_show_entitlement, 0) AS entitlement_based,
            1               AS is_active,
            COALESCE(lvtype_create_date, {now}) AS created_at,
            COALESCE(lvtype_update_date, lvtype_create_date, {now}) AS updated_at
        FROM hr_leavetype
        WHERE lvtype_id IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_leave_types", sql,
        [
            ("id", _int), ("code", _str), ("name", _str),
            ("is_paid", _bool), ("max_days_per_year", _float),
            ("carry_forward", _bool),
            ("requires_coverup", _bool), ("allow_attachment", _bool),
            ("attachment_mandatory", _bool), ("requires_approval", _bool),
            ("allow_half_day", _bool), ("entitlement_based", _bool),
            ("is_active", _bool),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
    )


def extract_leave_reason(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """hr_predefine_leave_purpose → stg_leave_reason (small lookup, full reload)."""
    sql = """
        SELECT
            predefine_leave_purpose_id AS id,
            predefine_leave_purpose    AS name,
            ref_legal_entity_id        AS legal_entity_id
        FROM hr_predefine_leave_purpose
        WHERE predefine_leave_purpose_id IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_leave_reason", sql,
        [
            ("id", _int),
            ("name", _str),
            ("legal_entity_id", _int),
        ],
    )


def extract_leave_requests(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    day_span = sql_date_diff_inclusive(
        "la.leave_start_date", "la.leave_end_date"
    )
    sql = f"""
        SELECT
            la.leave_id      AS id,
            la.ref_emp_id     AS employee_id,
            la.ref_lvtype_id  AS leave_type_id,
            la.leave_start_date AS start_date,
            la.leave_end_date   AS end_date,
            COALESCE(
                (SELECT SUM(d.dates_leave_count)
                 FROM hr_leaveapplication_dates d
                 WHERE d.dates_leave_id = la.leave_id),
                {day_span}
            )               AS days_requested,
            CASE
                WHEN la.leave_status = 1 THEN COALESCE(
                    (SELECT SUM(d.dates_leave_count)
                     FROM hr_leaveapplication_dates d
                     WHERE d.dates_leave_id = la.leave_id
                       AND d.dates_hr_approve = 1),
                    {day_span}
                )
                ELSE 0
            END             AS days_approved,
            CASE la.leave_status
                WHEN 0 THEN 'pending'
                WHEN 1 THEN 'approved'
                WHEN 2 THEN 'rejected'
                WHEN 3 THEN 'cancelled'
                ELSE 'unknown'
            END             AS status,
            la.leave_status AS status_code,
            la.leave_final_status AS final_status_code,
            la.leave_superior AS approved_by,
            la.leave_purpose  AS reason,
            la.ref_predefine_leave_purpose_id AS purpose_id,
            CASE WHEN COALESCE(la.is_hr_approval, 0) = 1 THEN 1 ELSE 0 END
                            AS is_hr_approval,
            la.leave_apply_date AS request_date,
            la.leave_approver_date AS approval_date,
            COALESCE(la.leave_apply_date, la.leave_start_date) AS created_at,
            COALESCE(la.leave_approver_date, la.leave_apply_date, la.leave_start_date)
                            AS updated_at
        FROM hr_leaveapplication la
        WHERE la.ref_emp_id IS NOT NULL
          AND la.leave_start_date IS NOT NULL
          AND la.leave_end_date IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_leave_requests", sql,
        [
            ("id", _int), ("employee_id", _int), ("leave_type_id", _int),
            ("start_date", _date), ("end_date", _date),
            ("days_requested", _float), ("days_approved", _float),
            ("status", _str), ("status_code", _int), ("final_status_code", _int),
            ("approved_by", _int), ("reason", _str), ("purpose_id", _int),
            ("is_hr_approval", _bool),
            ("request_date", _safe_datetime), ("approval_date", _safe_datetime),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_leave_application_dates(
    source: Engine, pg: Engine, tenant_id: str
) -> int:
    """Daily leave lines from hr_leaveapplication_dates (standard leave)."""
    approve_date = sql_zero_date_null("d.dates_approve_date")
    now = sql_now()
    sql = f"""
        SELECT
            d.dates_id              AS id,
            d.dates_leave_id        AS leave_application_id,
            d.dates_leave_date      AS leave_date,
            d.dates_status          AS day_status,
            d.dates_time_period     AS time_period,
            d.dates_leave_count     AS leave_day_count,
            d.dates_coverup_approve AS coverup_approved,
            d.dates_superior_approve AS superior_approved,
            d.dates_hr_approve      AS hr_approved,
            {approve_date}          AS approve_date,
            d.dates_leave_date      AS created_at,
            COALESCE({approve_date}, d.dates_leave_date, {now}) AS updated_at
        FROM hr_leaveapplication_dates d
        WHERE d.dates_leave_id IS NOT NULL
          AND d.dates_leave_date IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_leave_application_dates", sql,
        [
            ("id", _int), ("leave_application_id", _int),
            ("leave_date", _date),
            ("day_status", _int), ("time_period", _int),
            ("leave_day_count", _float),
            ("coverup_approved", _int), ("superior_approved", _int),
            ("hr_approved", _int), ("approve_date", _date),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
    )


def extract_leave_balance(
    source: Engine, pg: Engine, tenant_id: str
) -> int:
    """Runtime leave balances from hr_leave_balance."""
    now = sql_now()
    end_date = sql_zero_date_null("lb.leave_balance_end_date")
    sql = f"""
        SELECT
            lb.leave_balance_id           AS id,
            lb.ref_emp_id                 AS employee_id,
            lb.ref_lvtype_id              AS leave_type_id,
            lb.lvtype_name                AS leave_type_name,
            lb.leave_balance_entitlement  AS entitled_days,
            lb.leave_balance_approved     AS used_days,
            lb.leave_balance_count        AS remaining_days,
            lb.leave_balance_pending_for_approval AS pending_approval_days,
            lb.leave_balance_year         AS entitlement_year,
            lb.leave_balance_start_date   AS period_start_date,
            {end_date}                    AS period_end_date,
            COALESCE(lb.leave_balance_add_date, {now}) AS created_at,
            COALESCE(lb.leave_balance_add_date, {now}) AS updated_at
        FROM hr_leave_balance lb
        WHERE lb.ref_emp_id IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_leave_balance", sql,
        [
            ("id", _int), ("employee_id", _int), ("leave_type_id", _int),
            ("leave_type_name", _str),
            ("entitled_days", _float), ("used_days", _float),
            ("remaining_days", _float), ("pending_approval_days", _float),
            ("entitlement_year", _int),
            ("period_start_date", _date), ("period_end_date", _date),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
    )


def extract_leave_entitlement(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """Payroll entitlement rows from prl_leaveentitle (may be empty)."""
    start_date = sql_zero_date_null("e.lvqty_start_date")
    end_date = sql_zero_date_null("e.lvqty_end_date")
    now = sql_now()
    sql = f"""
        SELECT
            e.lventitle_id                AS id,
            e.ref_emp_id                  AS employee_id,
            e.ref_lvtype_id               AS leave_type_id,
            e.lvqty_entitle               AS entitled_days,
            e.lvqty_year                  AS entitlement_year,
            {start_date}                  AS period_start_date,
            {end_date}                    AS period_end_date,
            e.lvqty_status                AS status_code,
            e.lvqty_description           AS description,
            COALESCE(e.lvqty_request_date, {now}) AS created_at,
            COALESCE(e.lvqty_update_date, e.lvqty_request_date, {now}) AS updated_at
        FROM prl_leaveentitle e
        WHERE e.ref_emp_id IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_leave_entitlement", sql,
        [
            ("id", _int), ("employee_id", _int), ("leave_type_id", _int),
            ("entitled_days", _float), ("entitlement_year", _int),
            ("period_start_date", _date), ("period_end_date", _date),
            ("status_code", _int), ("description", _str),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_leave_approvals(
    source: Engine, pg: Engine, tenant_id: str
) -> int:
    """Standard leave approval actions from hr_leaveapplication_superiors."""
    now = sql_now()
    sql = f"""
        SELECT
            s.leave_sup_id                AS id,
            s.ref_leave_id                AS leave_application_id,
            s.leave_sup_approver          AS approver_employee_id,
            s.leave_sup_level             AS approval_level_code,
            s.leave_sup_approve_status    AS approval_status_code,
            CASE s.leave_sup_approve_status
                WHEN 1 THEN 'approved'
                WHEN 0 THEN 'pending'
                ELSE 'unknown'
            END                           AS approval_status,
            CASE s.leave_sup_level
                WHEN 1 THEN COALESCE(la.leave_first_approver_date, la.leave_approver_date)
                WHEN 2 THEN la.leave_second_approver_date
                WHEN 3 THEN la.leave_third_approver_date
                ELSE la.leave_approver_date
            END                           AS action_timestamp,
            la.leave_status               AS application_status_code,
            COALESCE(la.leave_approver_date, la.leave_apply_date, {now}) AS created_at,
            COALESCE(la.leave_approver_date, la.leave_apply_date, {now}) AS updated_at
        FROM hr_leaveapplication_superiors s
        INNER JOIN hr_leaveapplication la
            ON la.leave_id = s.ref_leave_id
        WHERE s.ref_leave_id IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_leave_approvals", sql,
        [
            ("id", _int), ("leave_application_id", _int),
            ("approver_employee_id", _int),
            ("approval_level_code", _int), ("approval_status_code", _int),
            ("approval_status", _str), ("action_timestamp", _safe_datetime),
            ("application_status_code", _int),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
    )


def _leave_status_from_codes(status_expr: str, final_expr: str) -> str:
    """MintHRM leave status text from status/final_status numeric columns."""
    return f"""
        CASE {final_expr}
            WHEN 1 THEN 'approved'
            WHEN 2 THEN 'rejected'
            WHEN 3 THEN 'cancelled'
            ELSE LOWER(TRIM(COALESCE({status_expr}, 'unknown')))
        END
    """


def extract_short_leave(
    source: Engine, pg: Engine, tenant_id: str
) -> int:
    now = sql_now()
    status = _leave_status_from_codes("sl.status", "sl.final_status")
    sql = f"""
        SELECT
            sl.id                       AS id,
            sl.ref_emp_id               AS employee_id,
            sl.deducted_leave_id        AS leave_type_id,
            sl.short_leave_date         AS short_leave_date,
            sl.start_time               AS start_time,
            sl.end_time                 AS end_time,
            GREATEST(
                TIMESTAMPDIFF(MINUTE, sl.start_time, sl.end_time) / 60.0,
                0
            )                           AS duration_hours,
            sl.time_category            AS time_category,
            sl.purpose                  AS purpose,
            {status}                    AS status,
            sl.approver_status          AS status_code,
            sl.final_status             AS final_status_code,
            sl.deducted_leave_id        AS deducted_leave_type_id,
            sl.apply_date               AS request_date,
            COALESCE(sl.approved_date, sl.is_hr_approval_date_time) AS approval_date,
            COALESCE(sl.apply_date, {now}) AS created_at,
            COALESCE(sl.approved_date, sl.apply_date, {now}) AS updated_at
        FROM hr_short_leave sl
        WHERE sl.ref_emp_id IS NOT NULL
          AND sl.short_leave_date IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_short_leave", sql,
        [
            ("id", _int), ("employee_id", _int), ("leave_type_id", _int),
            ("short_leave_date", _date),
            ("start_time", _safe_datetime), ("end_time", _safe_datetime),
            ("duration_hours", _float), ("time_category", _str), ("purpose", _str),
            ("status", _str), ("status_code", _int), ("final_status_code", _int),
            ("deducted_leave_type_id", _int),
            ("request_date", _safe_datetime), ("approval_date", _safe_datetime),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
    )


def extract_lieu_leave(
    source: Engine, pg: Engine, tenant_id: str
) -> int:
    now = sql_now()
    status = _leave_status_from_codes("'pending'", "ll.lieu_lv_final_status")
    sql = f"""
        SELECT
            ll.lieu_lv_id               AS id,
            ll.ref_emp_id               AS employee_id,
            ll.lieu_lv_date             AS leave_date,
            ll.lieu_lv_effective_date   AS effective_date,
            COALESCE(ll.lieu_lv_leave_count, 0) AS leave_day_count,
            ll.lieu_lv_time_period      AS time_period,
            {status}                    AS status,
            ll.lieu_lv_approver_status  AS status_code,
            ll.lieu_lv_final_status     AS final_status_code,
            ll.lieu_lv_comment          AS purpose,
            ll.lieu_lv_apply_date       AS request_date,
            COALESCE(
                ll.lieu_lv_approver_approved_date,
                ll.lieu_lv_second_approver_approved_date
            )                           AS approval_date,
            COALESCE(ll.lieu_lv_apply_date, {now}) AS created_at,
            COALESCE(
                ll.lieu_lv_approver_approved_date,
                ll.lieu_lv_apply_date,
                {now}
            )                           AS updated_at
        FROM hr_lieu_leave ll
        WHERE ll.ref_emp_id IS NOT NULL
          AND ll.lieu_lv_date IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_lieu_leave", sql,
        [
            ("id", _int), ("employee_id", _int),
            ("leave_date", _date), ("effective_date", _date),
            ("leave_day_count", _float), ("time_period", _int),
            ("status", _str), ("status_code", _int), ("final_status_code", _int),
            ("purpose", _str),
            ("request_date", _safe_datetime), ("approval_date", _safe_datetime),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
    )


def extract_lieu_leave_entitlement(
    source: Engine, pg: Engine, tenant_id: str
) -> int:
    now = sql_now()
    sql = f"""
        SELECT
            e.lieulv_id                 AS id,
            e.lieulv_emp_id             AS employee_id,
            e.lieulv_shift_day          AS calendar_date,
            COALESCE(e.lieulv_duration, 0) AS earned_days,
            e.lieulv_first_approver_status AS status_code,
            e.lieulv_final_status       AS final_status_code,
            e.lieulv_first_approver_status AS first_approver_status,
            e.lieulv_second_approver_status AS second_approver_status,
            COALESCE(e.lieulv_shift_day, {now}) AS created_at,
            COALESCE(
                e.lieulv_second_level_approved_time,
                e.lieulv_first_level_approved_time,
                e.lieulv_shift_day,
                {now}
            )                           AS updated_at
        FROM lieu_leave_entitlement_data e
        WHERE e.lieulv_emp_id IS NOT NULL
          AND e.lieulv_shift_day IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_lieu_leave_entitlement", sql,
        [
            ("id", _int), ("employee_id", _int), ("calendar_date", _date),
            ("earned_days", _float),
            ("status_code", _int), ("final_status_code", _int),
            ("first_approver_status", _int), ("second_approver_status", _int),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
    )


def extract_maternity_leave(
    source: Engine, pg: Engine, tenant_id: str
) -> int:
    now = sql_now()
    status = _leave_status_from_codes("m.maternity_previous_status", "m.maternity_ststus")
    sql = f"""
        SELECT
            m.maternity_id              AS id,
            CAST(NULLIF(TRIM(m.maternity_ref_emp_id), '') AS UNSIGNED) AS employee_id,
            m.ref_maternity_leave_setting_id AS leave_type_id,
            m.maternity_start_date      AS start_date,
            m.maternity_end_date        AS end_date,
            m.maternity_generated_end_date AS expected_end_date,
            m.maternity_child_count     AS child_count,
            {status}                    AS status,
            m.maternity_ststus          AS status_code,
            m.maternity_purpose         AS purpose,
            m.maternity_leave_created_date AS request_date,
            COALESCE(
                m.maternity_approval_level_two_date,
                m.maternity_approval_level_one_date
            )                           AS approval_date,
            COALESCE(m.maternity_leave_created_date, {now}) AS created_at,
            COALESCE(
                m.maternity_approval_level_two_date,
                m.maternity_approval_level_one_date,
                m.maternity_leave_created_date,
                {now}
            )                           AS updated_at
        FROM hr_leave_maternity m
        WHERE NULLIF(TRIM(m.maternity_ref_emp_id), '') IS NOT NULL
          AND m.maternity_start_date IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_maternity_leave", sql,
        [
            ("id", _int), ("employee_id", _int), ("leave_type_id", _int),
            ("start_date", _date), ("end_date", _date), ("expected_end_date", _date),
            ("child_count", _int),
            ("status", _str), ("status_code", _int), ("purpose", _str),
            ("request_date", _safe_datetime), ("approval_date", _safe_datetime),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
    )


def extract_leave_planner(
    source: Engine, pg: Engine, tenant_id: str
) -> int:
    now = sql_now()
    day_span = sql_date_diff_inclusive("p.leave_plan_from_date", "p.leave_plan_to_date")
    sql = f"""
        SELECT
            p.leave_plan_id             AS id,
            p.leave_plan_ref_emp_id     AS employee_id,
            CAST(NULLIF(TRIM(p.leave_plan_leave_type_id), '') AS UNSIGNED) AS leave_type_id,
            p.leave_plan_leave_type_code AS leave_type_code,
            p.leave_plan_from_date      AS planned_start_date,
            p.leave_plan_to_date        AS planned_end_date,
            COALESCE(
                (SELECT SUM(
                    CASE d.leave_plan_date_day_type
                        WHEN 1 THEN 0.5 ELSE 1
                    END
                 )
                 FROM hr_leave_planner_dates d
                 WHERE d.leave_plan_date_ref_id = p.leave_plan_id),
                {day_span}
            )                           AS planned_days,
            p.leave_plan_status         AS planner_status_code,
            CASE p.leave_plan_status
                WHEN 1 THEN 'approved'
                WHEN 2 THEN 'rejected'
                WHEN 0 THEN 'pending'
                ELSE 'unknown'
            END                         AS planner_status,
            p.leave_plan_leave_purpose  AS purpose,
            p.leave_plan_created_at     AS request_date,
            p.leave_plan_approved_reject_date AS approval_date,
            COALESCE(p.leave_plan_created_at, {now}) AS created_at,
            COALESCE(p.leave_plan_updated_at, p.leave_plan_created_at, {now}) AS updated_at
        FROM hr_leave_planner p
        WHERE p.leave_plan_ref_emp_id IS NOT NULL
          AND p.leave_plan_from_date IS NOT NULL
          AND p.leave_plan_to_date IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_leave_planner", sql,
        [
            ("id", _int), ("employee_id", _int), ("leave_type_id", _int),
            ("leave_type_code", _str),
            ("planned_start_date", _date), ("planned_end_date", _date),
            ("planned_days", _float),
            ("planner_status_code", _int), ("planner_status", _str),
            ("purpose", _str),
            ("request_date", _safe_datetime), ("approval_date", _safe_datetime),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
    )


def extract_performance_reviews(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """Placeholder — returns empty if pm tables unavailable."""
    now = sql_now()
    sql = f"""
        SELECT
            0 AS id, 0 AS employee_id, NULL AS reviewer_id,
            NULL AS review_period, NULL AS review_year,
            NULL AS overall_score, NULL AS rating, NULL AS status,
            NULL AS review_date, {now} AS created_at, {now} AS updated_at
        WHERE FALSE
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_performance_reviews", sql,
        [
            ("id", _int), ("employee_id", _int), ("reviewer_id", _int),
            ("review_period", _str), ("review_year", _int),
            ("overall_score", _float), ("rating", _str), ("status", _str),
            ("review_date", _date), ("created_at", None), ("updated_at", None),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col=None,
    )


def extract_training_records(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    now = sql_now()
    sql = f"""
        SELECT
            0 AS id, 0 AS employee_id, 0 AS training_id,
            NULL AS training_name, NULL AS training_type,
            NULL AS start_date, NULL AS end_date, NULL AS status,
            NULL AS score, NULL AS cost, {now} AS created_at, {now} AS updated_at
        WHERE FALSE
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_training_records", sql,
        [
            ("id", _int), ("employee_id", _int), ("training_id", _int),
            ("training_name", _str), ("training_type", _str),
            ("start_date", _date), ("end_date", _date), ("status", _str),
            ("score", _float), ("cost", _float),
            ("created_at", None), ("updated_at", None),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col=None,
    )


# Synthetic payroll run id: group + YYYYMM + half (matches MintHRM process grain)
def _payroll_run_id(
    group_col: str,
    year_col: str,
    month_col: str,
    half_col: str,
) -> str:
    return f"""
    (COALESCE({group_col}, 1) * 100000000
     + {year_col} * 10000
     + {month_col} * 100
     + COALESCE({half_col}, 0))
"""


_PAYROLL_RUN_ID = _payroll_run_id(
    "b.ref_payroll_group_id", "b.psb_proc_year", "b.psb_proc_month", "b.psb_proc_half"
)

_PAYROLL_RUN_ID_AD = _payroll_run_id(
    "b.ref_payroll_group_id", "ad.sad_proc_year", "ad.sad_proc_month", "ad.sad_proc_half"
)

_PAYROLL_RUN_ID_VA = _payroll_run_id(
    "b.ref_payroll_group_id", "va.vadd_proc_year", "va.vadd_proc_month", "va.vadd_proc_half"
)

_PAYROLL_RUN_ID_VD = _payroll_run_id(
    "b.ref_payroll_group_id", "vd.vded_proc_year", "vd.vded_proc_month", "vd.vded_proc_half"
)

_PAYROLL_RUN_ID_SA = _payroll_run_id(
    "b.ref_payroll_group_id", "sa.sa_proc_year", "sa.sa_proc_month", "sa.sa_proc_half"
)

_PAYROLL_RUN_ID_LN = _payroll_run_id(
    "b.ref_payroll_group_id", "ln.proc_ln_proc_year", "ln.proc_ln_proc_month", "ln.proc_ln_proc_half"
)

_PAYROLL_RUN_ID_IP = _payroll_run_id(
    "b.ref_payroll_group_id", "ip.proc_ipd_proc_year", "ip.proc_ipd_proc_month", "ip.proc_ipd_proc_half"
)

_PAYROLL_RUN_ID_TX = _payroll_run_id(
    "b.ref_payroll_group_id", "t.pt_proc_year", "t.pt_proc_month", "t.pt_proc_half"
)


def extract_payroll_groups(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """hr_payroll_groups (pg_id, pg_name, …) → raw_hr_payroll_groups."""
    now = sql_now()
    sql = f"""
        SELECT
            g.pg_id                                     AS id,
            NULLIF(TRIM(g.pg_name), '')                 AS payroll_group_name,
            g.pg_legal_entity_id                        AS legal_entity_id,
            COALESCE(NULLIF(TRIM(g.currency), ''), 'LKR')
                                                        AS currency_code,
            CASE
                WHEN COALESCE(g.pg_is_multicycle, 0) = 1
                  OR COALESCE(g.pg_cycles_per_month, 0) > 1
                THEN 'multicycle'
                ELSE 'monthly'
            END                                         AS payroll_frequency,
            1                                           AS is_active,
            COALESCE(g.is_available_epf8, 0)            AS is_available_epf8,
            COALESCE(g.is_available_epf12, 0)           AS is_available_epf12,
            COALESCE(g.is_available_etf3, 0)            AS is_available_etf3,
            COALESCE(g.is_available_tax, 0)           AS is_available_tax,
            COALESCE(g.is_stamp_duty, 0)              AS is_stamp_duty,
            NULLIF(TRIM(g.pg_registered_name), '')      AS pg_registered_name,
            NULLIF(TRIM(g.pg_epf_employer_no), '')     AS pg_epf_employer_no,
            COALESCE(g.consider_ot_for_payroll, 1)      AS consider_ot_for_payroll,
            COALESCE(g.consider_late_for_payroll, 1)    AS consider_late_for_payroll,
            COALESCE(g.consider_nopay_for_payroll, 1)   AS consider_nopay_for_payroll,
            COALESCE(g.pg_is_multicycle, 0)             AS pg_is_multicycle,
            COALESCE(g.pg_cycles_per_month, 0)          AS pg_cycles_per_month,
            COALESCE(g.pg_create_date, {now})           AS created_at,
            COALESCE(g.pg_update_date, g.pg_create_date, {now})
                                                        AS updated_at
        FROM hr_payroll_groups g
        WHERE g.pg_id IS NOT NULL
          AND NULLIF(TRIM(g.pg_name), '') IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "raw_hr_payroll_groups", sql,
        [
            ("id", _int), ("payroll_group_name", _str),
            ("legal_entity_id", _int), ("currency_code", _str),
            ("payroll_frequency", _str), ("is_active", _bool),
            ("is_available_epf8", _bool), ("is_available_epf12", _bool),
            ("is_available_etf3", _bool), ("is_available_tax", _bool),
            ("is_stamp_duty", _bool),
            ("pg_registered_name", _str), ("pg_epf_employer_no", _str),
            ("consider_ot_for_payroll", _bool),
            ("consider_late_for_payroll", _bool),
            ("consider_nopay_for_payroll", _bool),
            ("pg_is_multicycle", _bool), ("pg_cycles_per_month", _int),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_payroll_runs(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """Aggregate processed_sal_basic_data → stg_payroll_runs (per group / period)."""
    now = sql_now()
    run_code = sql_payroll_run_code(
        "ref_payroll_group_id", "psb_proc_year", "psb_proc_month", "psb_proc_half"
    )
    sql = f"""
        SELECT
            (COALESCE(ref_payroll_group_id, 1) * 100000000
             + psb_proc_year * 10000
             + psb_proc_month * 100
             + COALESCE(psb_proc_half, 0))             AS id,
            {run_code}                                  AS run_code,
            psb_proc_month                              AS payroll_month,
            psb_proc_year                               AS payroll_year,
            COALESCE(psb_proc_half, 0)                  AS payroll_half,
            'processed'                                 AS status,
            SUM(COALESCE(gross_salary_vw, psb_net_total
                + COALESCE(tot_ded_after_gross_vw, psb_total_deductions, 0)))
                                                        AS total_gross,
            SUM(COALESCE(tot_ded_after_gross_vw, psb_total_deductions, 0))
                                                        AS total_deductions,
            SUM(COALESCE(psb_net_total, 0))             AS total_net,
            MAX(psb_update_user)                        AS processed_by,
            MAX(psb_update_date)                        AS processed_at,
            MIN(COALESCE(psb_update_date, {now}))       AS created_at,
            MAX(COALESCE(psb_update_date, {now}))       AS updated_at
        FROM processed_sal_basic_data
        WHERE ref_emp_id IS NOT NULL
          AND psb_proc_year IS NOT NULL
          AND psb_proc_month IS NOT NULL
        GROUP BY ref_payroll_group_id, psb_proc_year, psb_proc_month, psb_proc_half
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_payroll_runs", sql,
        [
            ("id", _int), ("run_code", _str),
            ("payroll_month", _int), ("payroll_year", _int), ("payroll_half", _int),
            ("status", _str),
            ("total_gross", _float), ("total_deductions", _float), ("total_net", _float),
            ("processed_by", _int), ("processed_at", _safe_datetime),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_payroll_details(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """processed_sal_basic_data (+ add/ded / attendance rollups) → stg_payroll_details."""
    now = sql_now()
    sql = f"""
        SELECT
            b.psb_id                                      AS id,
            {_PAYROLL_RUN_ID.strip()}                     AS payroll_run_id,
            b.ref_emp_id                                  AS employee_id,
            COALESCE(b.psb_basic_or_day_salary, 0)
              + COALESCE(b.psb_basic_increment, 0)        AS basic_salary,
            COALESCE(ad.allowances, 0)                    AS allowances,
            COALESCE(att.overtime_pay, 0)                 AS overtime_pay,
            COALESCE(ad.bonuses, 0)                       AS bonuses,
            COALESCE(
                b.gross_salary_vw,
                b.psb_sub_total
                  + COALESCE(b.tot_ded_after_gross_vw, b.psb_total_deductions, 0)
            )                                             AS gross_salary,
            COALESCE(b.psb_tax, 0)                        AS tax_deduction,
            GREATEST(
                COALESCE(b.tot_ded_after_gross_vw, b.psb_total_deductions, 0)
                  - COALESCE(b.psb_tax, 0),
                0
            )                                             AS other_deductions,
            COALESCE(b.psb_net_total, 0)                  AS net_salary,
            COALESCE(b.psb_proc_half, 0)                  AS processing_half,
            b.ref_fortnight_id                            AS ref_fortnight_id,
            COALESCE(b.psb_epf8, 0)                       AS epf_employee_amount,
            COALESCE(b.psb_epf12, 0)                      AS epf_employer_amount,
            COALESCE(b.psb_epf3, 0)                       AS etf_amount,
            COALESCE(b.psb_paycut, 0)                     AS pay_cut_amount,
            COALESCE(b.psb_basic_increment, 0)            AS increment_amount,
            COALESCE(att.ot_amount, att.overtime_pay, 0)    AS ot_amount,
            COALESCE(ad.bonuses, 0)                         AS bonus_amount,
            COALESCE(att.attendance_deduction, 0)         AS attendance_deduction,
            COALESCE(att.nopay_deduction, 0)              AS nopay_deduction,
            COALESCE(ln.loan_deduction, 0)                AS loan_deduction,
            COALESCE(ip.installment_deduction, 0)         AS installment_deduction,
            CAST(0 AS DECIMAL(14,2))                      AS service_charge,
            COALESCE(NULLIF(TRIM(pg.currency), ''), 'LKR') AS currency_code,
            CAST(1 AS DECIMAL(14,6))                      AS exchange_rate,
            0                                               AS is_multi_currency,
            0                                               AS is_compliance_processed,
            'processed'                                     AS process_status,
            CAST(NULL AS SIGNED)                            AS original_process_reference,
            CAST(NULL AS DATETIME)                          AS reversal_timestamp,
            CAST(NULL AS SIGNED)                            AS reversed_by,
            CAST(NULL AS CHAR(255))                         AS reversal_reason,
            COALESCE(b.psb_update_date, {now})          AS created_at,
            COALESCE(b.psb_update_date, {now})          AS updated_at
        FROM processed_sal_basic_data b
        LEFT JOIN hr_payroll_groups pg ON pg.pg_id = b.ref_payroll_group_id
        LEFT JOIN (
            SELECT
                ref_emp_id,
                sad_proc_year,
                sad_proc_month,
                sad_proc_half,
                SUM(CASE
                    WHEN sad_type IN ('1', '3')
                      OR sad_type_name IN ('Fixed Addition', 'Variable Addition')
                    THEN COALESCE(sad_amount, 0) ELSE 0
                END) AS allowances,
                SUM(CASE
                    WHEN LOWER(COALESCE(sad_type_name, '')) LIKE '%bonus%'
                    THEN COALESCE(sad_amount, 0) ELSE 0
                END) AS bonuses
            FROM processed_sal_add_ded
            GROUP BY ref_emp_id, sad_proc_year, sad_proc_month, sad_proc_half
        ) ad ON ad.ref_emp_id = b.ref_emp_id
            AND ad.sad_proc_year = b.psb_proc_year
            AND ad.sad_proc_month = b.psb_proc_month
            AND COALESCE(ad.sad_proc_half, 0) = COALESCE(b.psb_proc_half, 0)
        LEFT JOIN (
            SELECT
                ref_emp_id,
                sa_proc_year,
                sa_proc_month,
                sa_proc_half,
                SUM(CASE
                    WHEN LOWER(COALESCE(sa_type_name, '')) LIKE '%overtime%'
                      OR LOWER(COALESCE(sa_type_name, '')) LIKE '%over time%'
                      OR LOWER(COALESCE(sa_type_name, '')) LIKE '% ot%'
                      OR LOWER(COALESCE(sa_type_name, '')) LIKE 'ot %'
                    THEN COALESCE(sa_amount, 0) ELSE 0
                END) AS overtime_pay,
                SUM(CASE
                    WHEN LOWER(COALESCE(sa_type_name, '')) LIKE '%overtime%'
                      OR LOWER(COALESCE(sa_type_name, '')) LIKE '%over time%'
                      OR LOWER(COALESCE(sa_type_name, '')) LIKE '% ot%'
                      OR LOWER(COALESCE(sa_type_name, '')) LIKE 'ot %'
                    THEN COALESCE(sa_amount, 0) ELSE 0
                END) AS ot_amount,
                SUM(CASE
                    WHEN LOWER(COALESCE(sa_type_name, '')) LIKE '%no pay%'
                      OR LOWER(COALESCE(sa_type_name, '')) LIKE '%nopay%'
                    THEN COALESCE(sa_amount, 0) ELSE 0
                END) AS nopay_deduction,
                SUM(CASE
                    WHEN LOWER(COALESCE(sa_type_name, '')) LIKE '%late%'
                      OR LOWER(COALESCE(sa_type_name, '')) LIKE '%absent%'
                    THEN COALESCE(sa_amount, 0) ELSE 0
                END) AS attendance_deduction
            FROM processed_sal_attendance
            GROUP BY ref_emp_id, sa_proc_year, sa_proc_month, sa_proc_half
        ) att ON att.ref_emp_id = b.ref_emp_id
            AND att.sa_proc_year = b.psb_proc_year
            AND att.sa_proc_month = b.psb_proc_month
            AND COALESCE(att.sa_proc_half, 0) = COALESCE(b.psb_proc_half, 0)
        LEFT JOIN (
            SELECT ref_emp_id, proc_ln_proc_year AS y, proc_ln_proc_month AS m,
                   proc_ln_proc_half AS h, SUM(COALESCE(proc_ln_amount, 0)) AS loan_deduction
            FROM processed_loan_data
            GROUP BY ref_emp_id, proc_ln_proc_year, proc_ln_proc_month, proc_ln_proc_half
        ) ln ON ln.ref_emp_id = b.ref_emp_id
            AND ln.y = b.psb_proc_year AND ln.m = b.psb_proc_month
            AND COALESCE(ln.h, 0) = COALESCE(b.psb_proc_half, 0)
        LEFT JOIN (
            SELECT ref_emp_id, proc_ipd_proc_year AS y, proc_ipd_proc_month AS m,
                   proc_ipd_proc_half AS h, SUM(COALESCE(proc_ipd_amount, 0)) AS installment_deduction
            FROM processed_installment_payment_data
            GROUP BY ref_emp_id, proc_ipd_proc_year, proc_ipd_proc_month, proc_ipd_proc_half
        ) ip ON ip.ref_emp_id = b.ref_emp_id
            AND ip.y = b.psb_proc_year AND ip.m = b.psb_proc_month
            AND COALESCE(ip.h, 0) = COALESCE(b.psb_proc_half, 0)
        WHERE b.ref_emp_id IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_payroll_details", sql,
        [
            ("id", _int), ("payroll_run_id", _int), ("employee_id", _int),
            ("basic_salary", _float), ("allowances", _float),
            ("overtime_pay", _float), ("bonuses", _float),
            ("gross_salary", _float), ("tax_deduction", _float),
            ("other_deductions", _float), ("net_salary", _float),
            ("processing_half", _int), ("ref_fortnight_id", _int),
            ("epf_employee_amount", _float), ("epf_employer_amount", _float),
            ("etf_amount", _float), ("pay_cut_amount", _float),
            ("increment_amount", _float),
            ("ot_amount", _float), ("bonus_amount", _float),
            ("attendance_deduction", _float), ("nopay_deduction", _float),
            ("loan_deduction", _float), ("installment_deduction", _float),
            ("service_charge", _float),
            ("currency_code", _str), ("exchange_rate", _float),
            ("is_multi_currency", _bool), ("is_compliance_processed", _bool),
            ("process_status", _str),
            ("original_process_reference", _int),
            ("reversal_timestamp", _safe_datetime),
            ("reversed_by", _int), ("reversal_reason", _str),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_payroll_add_ded(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """processed_sal_add_ded → stg_payroll_add_ded (line-level additions/deductions)."""
    now = sql_now()
    sql = f"""
        SELECT
            ad.sad_id                                     AS id,
            {_PAYROLL_RUN_ID_AD.strip()}                  AS payroll_run_id,
            ad.ref_emp_id                                 AS employee_id,
            ad.sad_type                                   AS line_type,
            ad.sad_type_name                              AS line_type_name,
            ad.sad_addorded_name                          AS component_name,
            COALESCE(ad.sad_amount, 0)                    AS amount,
            CASE WHEN COALESCE(ad.sad_epf_liable, 0) = 1 THEN 1 ELSE 0 END
                                                          AS is_epf_liable,
            ad.sad_proc_year                              AS proc_year,
            ad.sad_proc_month                             AS proc_month,
            COALESCE(ad.sad_proc_half, 0)                 AS proc_half,
            COALESCE(ad.sad_update_date, {now})           AS created_at,
            COALESCE(ad.sad_update_date, {now})           AS updated_at
        FROM processed_sal_add_ded ad
        LEFT JOIN processed_sal_basic_data b
            ON b.ref_emp_id = ad.ref_emp_id
           AND b.psb_proc_year = ad.sad_proc_year
           AND b.psb_proc_month = ad.sad_proc_month
           AND COALESCE(b.psb_proc_half, 0) = COALESCE(ad.sad_proc_half, 0)
        WHERE ad.ref_emp_id IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_payroll_add_ded", sql,
        [
            ("id", _int), ("payroll_run_id", _int), ("employee_id", _int),
            ("line_type", _str), ("line_type_name", _str), ("component_name", _str),
            ("amount", _float), ("is_epf_liable", _bool),
            ("proc_year", _int), ("proc_month", _int), ("proc_half", _int),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_payroll_attendance_lines(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """processed_sal_attendance → stg_payroll_attendance_lines."""
    now = sql_now()
    sql = f"""
        SELECT
            sa.sa_id                                      AS id,
            {_PAYROLL_RUN_ID_SA.strip()}                  AS payroll_run_id,
            sa.ref_emp_id                                 AS employee_id,
            {sql_cast_text('sa.sa_type')}                 AS line_type,
            sa.sa_type_name                               AS line_type_name,
            COALESCE(sa.sa_amount, 0)                     AS amount,
            sa.sa_value                                   AS value_text,
            sa.sa_proc_year                               AS proc_year,
            sa.sa_proc_month                              AS proc_month,
            COALESCE(sa.sa_proc_half, 0)                  AS proc_half,
            COALESCE(sa.sa_update_date, {now})            AS created_at,
            COALESCE(sa.sa_update_date, {now})            AS updated_at
        FROM processed_sal_attendance sa
        LEFT JOIN processed_sal_basic_data b
            ON b.ref_emp_id = sa.ref_emp_id
           AND b.psb_proc_year = sa.sa_proc_year
           AND b.psb_proc_month = sa.sa_proc_month
           AND COALESCE(b.psb_proc_half, 0) = COALESCE(sa.sa_proc_half, 0)
        WHERE sa.ref_emp_id IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_payroll_attendance_lines", sql,
        [
            ("id", _int), ("payroll_run_id", _int), ("employee_id", _int),
            ("line_type", _str), ("line_type_name", _str),
            ("amount", _float), ("value_text", _str),
            ("proc_year", _int), ("proc_month", _int), ("proc_half", _int),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_prl_overtime(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """prl_overtime → stg_prl_overtime (OT worksheet source)."""
    now = sql_now()
    ot_date = sql_safe_date_case("po.ot_date")
    proc_year = f"COALESCE(NULLIF(po.ot_processing_year, 0), {sql_year(ot_date)})"
    proc_month = f"COALESCE(NULLIF(po.ot_processing_month, 0), {sql_month(ot_date)})"
    inone_h = f"COALESCE({sql_time_to_seconds('po.ot_inone_amount')}, 0) / 3600.0"
    outone_h = f"COALESCE({sql_time_to_seconds('po.ot_outone_amount')}, 0) / 3600.0"
    ot_updated = f"COALESCE(TIMESTAMP({ot_date}), {now})"
    sql = f"""
        SELECT
            po.ot_id                                              AS id,
            po.ref_emp_id                                         AS employee_id,
            {proc_year}                                           AS proc_year,
            {proc_month}                                          AS proc_month,
            COALESCE(po.ot_processing_half, 0)                    AS proc_half,
            {inone_h}                                             AS ot_inone_hours,
            {outone_h}                                            AS ot_outone_hours,
            COALESCE(po.ot_dayorhour_amount, 0)                   AS ot_dayorhour_hours,
            {ot_updated}                                          AS created_at,
            {ot_updated}                                          AS updated_at
        FROM prl_overtime po
        WHERE po.ref_emp_id IS NOT NULL
          AND {proc_year} IS NOT NULL
          AND {proc_month} IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_prl_overtime", sql,
        [
            ("id", _int), ("employee_id", _int),
            ("proc_year", _int), ("proc_month", _int), ("proc_half", _int),
            ("ot_inone_hours", _float), ("ot_outone_hours", _float),
            ("ot_dayorhour_hours", _float),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
        incremental_by_pk=True,
    )


def extract_payroll_variable_additions(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """prl_variableadditions_forsal → stg_payroll_variable_additions."""
    now = sql_now()
    sql = f"""
        SELECT
            va.vadd_id                                    AS id,
            {_PAYROLL_RUN_ID_VA.strip()}                  AS payroll_run_id,
            va.ref_emp_id                                 AS employee_id,
            va.ref_vadd_id                                AS ref_component_id,
            COALESCE(va.vadd_quantity, 0)                 AS quantity,
            COALESCE(va.vadd_peramount, 0)                AS rate,
            COALESCE(va.vadd_amount, 0)                   AS amount,
            va.vadd_proc_year                             AS proc_year,
            va.vadd_proc_month                            AS proc_month,
            COALESCE(va.vadd_proc_half, 0)                AS proc_half,
            COALESCE(va.vadd_update_date, {now})          AS created_at,
            COALESCE(va.vadd_update_date, {now})          AS updated_at
        FROM prl_variableadditions_forsal va
        LEFT JOIN processed_sal_basic_data b
            ON b.ref_emp_id = va.ref_emp_id
           AND b.psb_proc_year = va.vadd_proc_year
           AND b.psb_proc_month = va.vadd_proc_month
           AND COALESCE(b.psb_proc_half, 0) = COALESCE(va.vadd_proc_half, 0)
        WHERE va.ref_emp_id IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_payroll_variable_additions", sql,
        [
            ("id", _int), ("payroll_run_id", _int), ("employee_id", _int),
            ("ref_component_id", _int),
            ("quantity", _float), ("rate", _float), ("amount", _float),
            ("proc_year", _int), ("proc_month", _int), ("proc_half", _int),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_payroll_variable_deductions(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """prl_variabledeductions_forsal → stg_payroll_variable_deductions."""
    now = sql_now()
    sql = f"""
        SELECT
            vd.vded_id                                    AS id,
            {_PAYROLL_RUN_ID_VD.strip()}                  AS payroll_run_id,
            vd.ref_emp_id                                 AS employee_id,
            vd.ref_vded_id                                AS ref_component_id,
            COALESCE(vd.vded_quantity, 0)                 AS quantity,
            COALESCE(vd.vded_peramount, 0)                AS rate,
            COALESCE(vd.vded_amount, 0)                   AS amount,
            vd.vded_proc_year                             AS proc_year,
            vd.vded_proc_month                            AS proc_month,
            COALESCE(vd.vded_proc_half, 0)                AS proc_half,
            COALESCE(vd.vded_update_date, {now})          AS created_at,
            COALESCE(vd.vded_update_date, {now})          AS updated_at
        FROM prl_variabledeductions_forsal vd
        LEFT JOIN processed_sal_basic_data b
            ON b.ref_emp_id = vd.ref_emp_id
           AND b.psb_proc_year = vd.vded_proc_year
           AND b.psb_proc_month = vd.vded_proc_month
           AND COALESCE(b.psb_proc_half, 0) = COALESCE(vd.vded_proc_half, 0)
        WHERE vd.ref_emp_id IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_payroll_variable_deductions", sql,
        [
            ("id", _int), ("payroll_run_id", _int), ("employee_id", _int),
            ("ref_component_id", _int),
            ("quantity", _float), ("rate", _float), ("amount", _float),
            ("proc_year", _int), ("proc_month", _int), ("proc_half", _int),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_payroll_tax(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """processed_tax_data_for_employee → stg_payroll_tax."""
    now = sql_now()
    sql = f"""
        SELECT
            t.pt_id                                       AS id,
            {_PAYROLL_RUN_ID_TX.strip()}                  AS payroll_run_id,
            t.ref_emp_id                                  AS employee_id,
            {sql_cast_text('t.ref_tax_id')}               AS tax_component_code,
            NULLIF(TRIM(t.pt_tax_name), '')               AS tax_component_name,
            COALESCE(t.pt_calculated_tax_amount, 0)         AS tax_amount,
            COALESCE(t.pt_taxable_amount, 0)              AS taxable_amount,
            CAST(0 AS DECIMAL(14, 2))                     AS tax_relief_amount,
            CAST(0 AS DECIMAL(8, 4))                      AS tax_percentage,
            COALESCE(t.pt_taxable_amount, 0) * 12         AS annualized_taxable_income,
            t.pt_proc_year                                AS proc_year,
            t.pt_proc_month                               AS proc_month,
            COALESCE(t.pt_proc_half, 0)                   AS proc_half,
            COALESCE(t.pt_update_date, {now})             AS created_at,
            COALESCE(t.pt_update_date, {now})             AS updated_at
        FROM processed_tax_data_for_employee t
        LEFT JOIN processed_sal_basic_data b
            ON b.ref_emp_id = t.ref_emp_id
           AND b.psb_proc_year = t.pt_proc_year
           AND b.psb_proc_month = t.pt_proc_month
           AND COALESCE(b.psb_proc_half, 0) = COALESCE(t.pt_proc_half, 0)
        WHERE t.ref_emp_id IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_payroll_tax", sql,
        [
            ("id", _int), ("payroll_run_id", _int), ("employee_id", _int),
            ("tax_component_code", _str), ("tax_component_name", _str),
            ("tax_amount", _float), ("taxable_amount", _float),
            ("tax_relief_amount", _float), ("tax_percentage", _float),
            ("annualized_taxable_income", _float),
            ("proc_year", _int), ("proc_month", _int), ("proc_half", _int),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_payroll_loan_deductions(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """processed_loan_data + installment payments → stg_payroll_loan_deductions."""
    now = sql_now()
    sql = f"""
        SELECT
            ln.proc_ln_id                                 AS id,
            {_PAYROLL_RUN_ID_LN.strip()}                  AS payroll_run_id,
            ln.ref_emp_id                                 AS employee_id,
            'loan'                                        AS deduction_type,
            NULLIF(TRIM(ln.proc_loan_type_name), '')       AS deduction_name,
            COALESCE(ln.proc_ln_amount, 0)                AS amount,
            ln.proc_ln_proc_year                          AS proc_year,
            ln.proc_ln_proc_month                         AS proc_month,
            COALESCE(ln.proc_ln_proc_half, 0)             AS proc_half,
            COALESCE(ln.proc_ln_update_date, {now})         AS created_at,
            COALESCE(ln.proc_ln_update_date, {now})         AS updated_at
        FROM processed_loan_data ln
        LEFT JOIN processed_sal_basic_data b
            ON b.ref_emp_id = ln.ref_emp_id
           AND b.psb_proc_year = ln.proc_ln_proc_year
           AND b.psb_proc_month = ln.proc_ln_proc_month
           AND COALESCE(b.psb_proc_half, 0) = COALESCE(ln.proc_ln_proc_half, 0)
        WHERE ln.ref_emp_id IS NOT NULL
        UNION ALL
        SELECT
            ip.proc_ipd_id + 1000000000                   AS id,
            {_PAYROLL_RUN_ID_IP.strip()}                  AS payroll_run_id,
            ip.ref_emp_id                                 AS employee_id,
            'installment'                                 AS deduction_type,
            NULLIF(TRIM(ip.proc_ipd_type_name), '')       AS deduction_name,
            COALESCE(ip.proc_ipd_amount, 0)               AS amount,
            ip.proc_ipd_proc_year                         AS proc_year,
            ip.proc_ipd_proc_month                        AS proc_month,
            COALESCE(ip.proc_ipd_proc_half, 0)            AS proc_half,
            COALESCE(ip.proc_update_date, {now})          AS created_at,
            COALESCE(ip.proc_update_date, {now})          AS updated_at
        FROM processed_installment_payment_data ip
        LEFT JOIN processed_sal_basic_data b
            ON b.ref_emp_id = ip.ref_emp_id
           AND b.psb_proc_year = ip.proc_ipd_proc_year
           AND b.psb_proc_month = ip.proc_ipd_proc_month
           AND COALESCE(b.psb_proc_half, 0) = COALESCE(ip.proc_ipd_proc_half, 0)
        WHERE ip.ref_emp_id IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_payroll_loan_deductions", sql,
        [
            ("id", _int), ("payroll_run_id", _int), ("employee_id", _int),
            ("deduction_type", _str), ("deduction_name", _str),
            ("amount", _float),
            ("proc_year", _int), ("proc_month", _int), ("proc_half", _int),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=incremental,
        pk_column="id",
        watermark_col="updated_at",
    )


def extract_payroll_salary_retrieve(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """prl_salary_retrieve → stg_payroll_salary_retrieve (employee-level payment setup)."""
    m = _m()
    now = sql_now()
    r = "r"
    sql = f"""
        SELECT
            {m.ref('payroll_salary_retrieve', 'id', r)}      AS id,
            {sql_cast_signed_int('NULL')}                    AS payroll_run_id,
            {m.ref('payroll_salary_retrieve', 'ref_emp_id', r)} AS employee_id,
            CASE WHEN COALESCE({m.ref('payroll_salary_retrieve', 'is_bank', r)}, 0) = 1
                THEN 1 ELSE 0 END                            AS is_bank,
            {sql_cast_signed_int('NULL')}                    AS proc_year,
            {sql_cast_signed_int('NULL')}                    AS proc_month,
            {sql_cast_signed_int('0')}                       AS proc_half,
            COALESCE({m.ref('payroll_salary_retrieve', 'modified_date', r)}, {now})
                                                            AS created_at,
            COALESCE({m.ref('payroll_salary_retrieve', 'modified_date', r)}, {now})
                                                            AS updated_at
        FROM {m.table('payroll_salary_retrieve')} {r}
        WHERE {m.ref('payroll_salary_retrieve', 'id', r)} IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_payroll_salary_retrieve", sql,
        [
            ("id", _int), ("payroll_run_id", _int), ("employee_id", _int),
            ("is_bank", _bool),
            ("proc_year", _int), ("proc_month", _int), ("proc_half", _int),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=False,
        pk_column="id",
        watermark_col=None,
    )


def extract_payroll_salary_bank_data(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """prl_salary_bank_data → stg_payroll_salary_bank_data (bank account split rows)."""
    m = _m()
    now = sql_now()
    d = "d"
    sql = f"""
        SELECT
            {m.ref('payroll_salary_bank_data', 'id', d)}       AS id,
            {m.ref('payroll_salary_bank_data', 'ref_retrieve_id', d)}
                                                            AS ref_retrieve_id,
            {m.ref('payroll_salary_bank_data', 'bank_id', d)}   AS bank_id,
            {m.ref('payroll_salary_bank_data', 'bank_branch_id', d)}
                                                            AS bank_branch_id,
            NULLIF(TRIM({m.ref('payroll_salary_bank_data', 'bank_acc_no', d)}), '')
                                                            AS bank_acc_no,
            COALESCE({m.ref('payroll_salary_bank_data', 'bank_amount', d)}, 0)
                                                            AS bank_amount,
            NULLIF(TRIM({m.ref('payroll_salary_bank_data', 'bank_passbook_name', d)}), '')
                                                            AS bank_passbook_name,
            CASE WHEN COALESCE({m.ref('payroll_salary_bank_data', 'is_primary_account', d)}, 0) = 1
                THEN 1 ELSE 0 END                            AS is_primary_account,
            COALESCE({m.ref('payroll_salary_bank_data', 'modified_date', d)}, {now})
                                                            AS created_at,
            COALESCE({m.ref('payroll_salary_bank_data', 'modified_date', d)}, {now})
                                                            AS updated_at
        FROM {m.table('payroll_salary_bank_data')} {d}
        WHERE {m.ref('payroll_salary_bank_data', 'id', d)} IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_payroll_salary_bank_data", sql,
        [
            ("id", _int), ("ref_retrieve_id", _int),
            ("bank_id", _int), ("bank_branch_id", _int),
            ("bank_acc_no", _str), ("bank_amount", _float),
            ("bank_passbook_name", _str), ("is_primary_account", _bool),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=False,
        pk_column="id",
        watermark_col=None,
    )


def extract_payroll_bank(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """bank → stg_payroll_bank (bank master)."""
    m = _m()
    now = sql_now()
    b = "b"
    sql = f"""
        SELECT
            {m.ref('payroll_bank', 'id', b)}                  AS id,
            NULLIF(TRIM({m.ref('payroll_bank', 'bank_code', b)}), '')
                                                            AS bank_code,
            NULLIF(TRIM({m.ref('payroll_bank', 'bank_name', b)}), '')
                                                            AS bank_name,
            COALESCE({m.ref('payroll_bank', 'create_date', b)},
                     {m.ref('payroll_bank', 'modified_date', b)}, {now})
                                                            AS created_at,
            COALESCE({m.ref('payroll_bank', 'modified_date', b)}, {now})
                                                            AS updated_at
        FROM {m.table('payroll_bank')} {b}
        WHERE {m.ref('payroll_bank', 'id', b)} IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_payroll_bank", sql,
        [
            ("id", _int), ("bank_code", _str), ("bank_name", _str),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=False,
        pk_column="id",
        watermark_col=None,
    )


def extract_payroll_bank_branch(
    source: Engine, pg: Engine, tenant_id: str, *, incremental: bool = False
) -> int:
    """mas_branch → stg_payroll_bank_branch (bank branch master)."""
    m = _m()
    now = sql_now()
    mb = "mb"
    sql = f"""
        SELECT
            {m.ref('payroll_bank_branch', 'id', mb)}          AS id,
            {m.ref('payroll_bank_branch', 'ref_bank_id', mb)} AS ref_bank_id,
            NULLIF(TRIM({m.ref('payroll_bank_branch', 'branch_code', mb)}), '')
                                                            AS branch_code,
            NULLIF(TRIM({m.ref('payroll_bank_branch', 'branch_name', mb)}), '')
                                                            AS branch_name,
            COALESCE({m.ref('payroll_bank_branch', 'create_date', mb)},
                     {m.ref('payroll_bank_branch', 'modified_date', mb)}, {now})
                                                            AS created_at,
            COALESCE({m.ref('payroll_bank_branch', 'modified_date', mb)}, {now})
                                                            AS updated_at
        FROM {m.table('payroll_bank_branch')} {mb}
        WHERE {m.ref('payroll_bank_branch', 'id', mb)} IS NOT NULL
    """
    return _stream_extract(
        source, pg, tenant_id, "stg_payroll_bank_branch", sql,
        [
            ("id", _int), ("ref_bank_id", _int),
            ("branch_code", _str), ("branch_name", _str),
            ("created_at", _safe_datetime), ("updated_at", _safe_datetime),
        ],
        incremental=False,
        pk_column="id",
        watermark_col=None,
    )


from app.services.hr_etl.extractors_payroll_phase6 import (  # noqa: E402
    PHASE6_EXTRACTORS,
    PHASE6_INCREMENTAL_TABLES,
)
from app.services.hr_etl.payroll_source import optional_extractor  # noqa: E402

BANK_PAYROLL_EXTRACTORS: list[tuple[str, Callable]] = [
    (
        "stg_payroll_salary_retrieve",
        optional_extractor(
            "prl_salary_retrieve",
            extract_payroll_salary_retrieve,
            "retrieve_id",
            "ref_emp_id",
            "is_bank",
        ),
    ),
    (
        "stg_payroll_salary_bank_data",
        optional_extractor(
            "prl_salary_bank_data",
            extract_payroll_salary_bank_data,
            "bank_id",
            "ref_retrieve_id",
            "bank_name",
            "bank_branch",
            "bank_acc_no",
            "bank_amount",
            "bank_passbook_name",
            "is_primary_account",
        ),
    ),
    (
        "stg_payroll_bank",
        optional_extractor(
            "bank",
            extract_payroll_bank,
            "id",
            "bank_code",
            "bank_name",
        ),
    ),
    (
        "stg_payroll_bank_branch",
        optional_extractor(
            "mas_branch",
            extract_payroll_bank_branch,
            "id",
            "ref_bank_id",
            "branch_code",
            "branch_name",
        ),
    ),
]

EXTRACTORS: list[tuple[str, Callable]] = [
    ("stg_branches", extract_branches),
    ("stg_departments", extract_departments),
    ("stg_company_hierarchy_individual", extract_company_hierarchy_individual),
    ("stg_designations", extract_designations),
    ("stg_leave_types", extract_leave_types),
    ("stg_leave_reason", extract_leave_reason),
    ("stg_employees", extract_employees),
    ("stg_lifecycle", extract_lifecycle),
    ("raw_hr_payroll_groups", extract_payroll_groups),
    ("stg_payroll_runs", extract_payroll_runs),
    ("stg_payroll_details", extract_payroll_details),
    ("stg_payroll_add_ded", extract_payroll_add_ded),
    ("stg_payroll_attendance_lines", extract_payroll_attendance_lines),
    ("stg_prl_overtime", extract_prl_overtime),
    ("stg_payroll_variable_additions", extract_payroll_variable_additions),
    ("stg_payroll_variable_deductions", extract_payroll_variable_deductions),
    ("stg_payroll_tax", extract_payroll_tax),
    ("stg_payroll_loan_deductions", extract_payroll_loan_deductions),
    *BANK_PAYROLL_EXTRACTORS,
    *PHASE6_EXTRACTORS,
    ("stg_attendance", extract_attendance),
    ("stg_leave_requests", extract_leave_requests),
    ("stg_leave_application_dates", extract_leave_application_dates),
    ("stg_leave_balance", extract_leave_balance),
    ("stg_leave_entitlement", extract_leave_entitlement),
    ("stg_leave_approvals", extract_leave_approvals),
    ("stg_short_leave", extract_short_leave),
    ("stg_lieu_leave", extract_lieu_leave),
    ("stg_lieu_leave_entitlement", extract_lieu_leave_entitlement),
    ("stg_maternity_leave", extract_maternity_leave),
    ("stg_leave_planner", extract_leave_planner),
    ("stg_performance_reviews", extract_performance_reviews),
    ("stg_training_records", extract_training_records),
]

INCREMENTAL_TABLES: set[str] = {
    "stg_employees",
    "stg_lifecycle",
    "stg_attendance",
    "stg_leave_requests",
    "stg_leave_entitlement",
    "stg_designations",
    "stg_branches",
    "raw_hr_payroll_groups",
    "stg_payroll_runs",
    "stg_payroll_details",
    "stg_payroll_add_ded",
    "stg_payroll_attendance_lines",
    "stg_prl_overtime",
    "stg_payroll_variable_additions",
    "stg_payroll_variable_deductions",
    "stg_payroll_tax",
    "stg_payroll_loan_deductions",
    *PHASE6_INCREMENTAL_TABLES,
}
