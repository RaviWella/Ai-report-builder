"""Staging table DDL — shared by ETL auto-create and init scripts."""
from __future__ import annotations

STAGING_DDL: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_branches (
        id INTEGER PRIMARY KEY,
        code VARCHAR(64),
        name VARCHAR(255),
        region VARCHAR(128),
        country VARCHAR(128),
        is_active BOOLEAN,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_departments (
        id INTEGER PRIMARY KEY,
        code VARCHAR(64),
        name VARCHAR(255),
        parent_id INTEGER,
        head_employee_id INTEGER,
        is_active BOOLEAN,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_company_hierarchy_individual (
        id INTEGER PRIMARY KEY,
        ref_emp_id INTEGER NOT NULL,
        parent_id INTEGER,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_designations (
        id INTEGER PRIMARY KEY,
        code VARCHAR(64),
        title VARCHAR(255),
        grade VARCHAR(64),
        department_id INTEGER,
        is_active BOOLEAN,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_leave_types (
        id INTEGER PRIMARY KEY,
        code VARCHAR(64),
        name VARCHAR(255),
        is_paid BOOLEAN,
        max_days_per_year NUMERIC(8,2),
        carry_forward BOOLEAN,
        requires_coverup BOOLEAN,
        allow_attachment BOOLEAN,
        attachment_mandatory BOOLEAN,
        requires_approval BOOLEAN,
        allow_half_day BOOLEAN,
        entitlement_based BOOLEAN,
        is_active BOOLEAN,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_leave_reason (
        id INTEGER PRIMARY KEY,
        name VARCHAR(255),
        legal_entity_id INTEGER,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_employees (
        id INTEGER PRIMARY KEY,
        employee_code VARCHAR(64),
        first_name VARCHAR(128),
        last_name VARCHAR(128),
        full_name VARCHAR(255),
        gender VARCHAR(32),
        date_of_birth DATE,
        national_id VARCHAR(64),
        email VARCHAR(255),
        phone VARCHAR(64),
        department_id INTEGER,
        designation_id INTEGER,
        branch_id INTEGER,
        cost_center_id INTEGER,
        employment_type VARCHAR(64),
        employment_status VARCHAR(64),
        date_joined DATE,
        date_confirmed DATE,
        date_resigned DATE,
        date_terminated DATE,
        reporting_to INTEGER,
        legal_entity_id INTEGER,
        legal_entity_name VARCHAR(255),
        legal_entity_code VARCHAR(64),
        designation_name VARCHAR(255),
        designation_department VARCHAR(255),
        grade_name VARCHAR(64),
        employee_category VARCHAR(128),
        employee_category_code VARCHAR(64),
        location_name VARCHAR(255),
        basic_salary NUMERIC(14, 2),
        epf_no VARCHAR(64),
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_attendance (
        id INTEGER PRIMARY KEY,
        employee_id INTEGER,
        attendance_date DATE,
        check_in TIMESTAMPTZ,
        check_out TIMESTAMPTZ,
        status VARCHAR(64),
        late_minutes INTEGER,
        early_leave_minutes INTEGER,
        overtime_minutes INTEGER,
        work_hours NUMERIC(8,2),
        shift_id INTEGER,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_leave_requests (
        id INTEGER PRIMARY KEY,
        employee_id INTEGER,
        leave_type_id INTEGER,
        start_date DATE,
        end_date DATE,
        days_requested NUMERIC(8,2),
        days_approved NUMERIC(8,2),
        status VARCHAR(64),
        status_code INTEGER,
        final_status_code INTEGER,
        approved_by INTEGER,
        reason TEXT,
        purpose_id INTEGER,
        is_hr_approval BOOLEAN,
        request_date TIMESTAMPTZ,
        approval_date TIMESTAMPTZ,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_leave_application_dates (
        id INTEGER PRIMARY KEY,
        leave_application_id INTEGER NOT NULL,
        leave_date DATE NOT NULL,
        day_status INTEGER,
        time_period INTEGER,
        leave_day_count NUMERIC(8,2),
        coverup_approved INTEGER,
        superior_approved INTEGER,
        hr_approved INTEGER,
        approve_date DATE,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_leave_balance (
        id INTEGER PRIMARY KEY,
        employee_id INTEGER NOT NULL,
        leave_type_id INTEGER,
        leave_type_name VARCHAR(255),
        entitled_days NUMERIC(10,2),
        used_days NUMERIC(10,2),
        remaining_days NUMERIC(10,2),
        pending_approval_days NUMERIC(10,2),
        entitlement_year INTEGER,
        period_start_date DATE,
        period_end_date DATE,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_leave_entitlement (
        id INTEGER PRIMARY KEY,
        employee_id INTEGER NOT NULL,
        leave_type_id INTEGER,
        entitled_days NUMERIC(10,2),
        entitlement_year INTEGER,
        period_start_date DATE,
        period_end_date DATE,
        status_code INTEGER,
        description TEXT,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_leave_approvals (
        id INTEGER PRIMARY KEY,
        leave_application_id INTEGER NOT NULL,
        approver_employee_id INTEGER,
        approval_level_code INTEGER,
        approval_status_code INTEGER,
        approval_status VARCHAR(64),
        action_timestamp TIMESTAMPTZ,
        application_status_code INTEGER,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_short_leave (
        id INTEGER PRIMARY KEY,
        employee_id INTEGER NOT NULL,
        leave_type_id INTEGER,
        short_leave_date DATE,
        start_time TIMESTAMPTZ,
        end_time TIMESTAMPTZ,
        duration_hours NUMERIC(8,2),
        time_category VARCHAR(64),
        purpose TEXT,
        status VARCHAR(64),
        status_code INTEGER,
        final_status_code INTEGER,
        deducted_leave_type_id INTEGER,
        request_date TIMESTAMPTZ,
        approval_date TIMESTAMPTZ,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_lieu_leave (
        id INTEGER PRIMARY KEY,
        employee_id INTEGER NOT NULL,
        leave_date DATE,
        effective_date DATE,
        leave_day_count NUMERIC(8,2),
        time_period INTEGER,
        status VARCHAR(64),
        status_code INTEGER,
        final_status_code INTEGER,
        purpose TEXT,
        request_date TIMESTAMPTZ,
        approval_date TIMESTAMPTZ,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_lieu_leave_entitlement (
        id INTEGER PRIMARY KEY,
        employee_id INTEGER NOT NULL,
        calendar_date DATE,
        earned_days NUMERIC(8,2),
        status_code INTEGER,
        final_status_code INTEGER,
        first_approver_status INTEGER,
        second_approver_status INTEGER,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_maternity_leave (
        id INTEGER PRIMARY KEY,
        employee_id INTEGER NOT NULL,
        leave_type_id INTEGER,
        start_date DATE,
        end_date DATE,
        expected_end_date DATE,
        child_count INTEGER,
        status VARCHAR(64),
        status_code INTEGER,
        purpose TEXT,
        request_date TIMESTAMPTZ,
        approval_date TIMESTAMPTZ,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_leave_planner (
        id INTEGER PRIMARY KEY,
        employee_id INTEGER NOT NULL,
        leave_type_id INTEGER,
        leave_type_code VARCHAR(64),
        planned_start_date DATE,
        planned_end_date DATE,
        planned_days NUMERIC(8,2),
        planner_status_code INTEGER,
        planner_status VARCHAR(64),
        purpose TEXT,
        request_date TIMESTAMPTZ,
        approval_date TIMESTAMPTZ,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_payroll_runs (
        id INTEGER PRIMARY KEY,
        run_code VARCHAR(64),
        payroll_month INTEGER,
        payroll_year INTEGER,
        status VARCHAR(64),
        total_gross NUMERIC(14,2),
        total_deductions NUMERIC(14,2),
        total_net NUMERIC(14,2),
        processed_by INTEGER,
        processed_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_payroll_details (
        id INTEGER PRIMARY KEY,
        payroll_run_id INTEGER,
        employee_id INTEGER,
        basic_salary NUMERIC(14,2),
        allowances NUMERIC(14,2),
        overtime_pay NUMERIC(14,2),
        bonuses NUMERIC(14,2),
        gross_salary NUMERIC(14,2),
        tax_deduction NUMERIC(14,2),
        other_deductions NUMERIC(14,2),
        net_salary NUMERIC(14,2),
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_payroll_add_ded (
        id INTEGER PRIMARY KEY,
        payroll_run_id INTEGER,
        employee_id INTEGER,
        line_type VARCHAR(64),
        line_type_name VARCHAR(255),
        component_name VARCHAR(255),
        amount NUMERIC(14,2),
        is_epf_liable BOOLEAN,
        proc_year INTEGER,
        proc_month INTEGER,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_payroll_attendance_lines (
        id INTEGER PRIMARY KEY,
        payroll_run_id INTEGER,
        employee_id INTEGER,
        line_type VARCHAR(64),
        line_type_name VARCHAR(255),
        amount NUMERIC(14,2),
        value_text VARCHAR(255),
        proc_year INTEGER,
        proc_month INTEGER,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_payroll_variable_additions (
        id INTEGER PRIMARY KEY,
        payroll_run_id INTEGER,
        employee_id INTEGER,
        ref_component_id INTEGER,
        quantity NUMERIC(14,4),
        rate NUMERIC(14,4),
        amount NUMERIC(14,2),
        proc_year INTEGER,
        proc_month INTEGER,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_payroll_variable_deductions (
        id INTEGER PRIMARY KEY,
        payroll_run_id INTEGER,
        employee_id INTEGER,
        ref_component_id INTEGER,
        quantity NUMERIC(14,4),
        rate NUMERIC(14,4),
        amount NUMERIC(14,2),
        proc_year INTEGER,
        proc_month INTEGER,
        proc_half INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_payroll_tax (
        id BIGINT PRIMARY KEY,
        payroll_run_id INTEGER,
        employee_id INTEGER,
        tax_component_code VARCHAR(64),
        tax_component_name VARCHAR(255),
        tax_amount NUMERIC(14,2),
        taxable_amount NUMERIC(14,2),
        proc_year INTEGER,
        proc_month INTEGER,
        proc_half INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_prl_overtime (
        id BIGINT PRIMARY KEY,
        employee_id INTEGER,
        proc_year INTEGER,
        proc_month INTEGER,
        proc_half INTEGER DEFAULT 0,
        ot_inone_hours NUMERIC(14, 4),
        ot_outone_hours NUMERIC(14, 4),
        ot_dayorhour_hours NUMERIC(14, 4),
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_payroll_loan_deductions (
        id BIGINT PRIMARY KEY,
        payroll_run_id INTEGER,
        employee_id INTEGER,
        deduction_type VARCHAR(32),
        deduction_name VARCHAR(255),
        amount NUMERIC(14,2),
        proc_year INTEGER,
        proc_month INTEGER,
        proc_half INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_payroll_loan_data (
        id INTEGER PRIMARY KEY,
        payroll_run_id INTEGER,
        employee_id INTEGER,
        loan_id INTEGER,
        installment_id INTEGER,
        installment_no INTEGER,
        deduction_name VARCHAR(255),
        amount NUMERIC(14,2),
        remaining_balance NUMERIC(14,2),
        is_final_installment BOOLEAN,
        proc_year INTEGER,
        proc_month INTEGER,
        proc_half INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_payroll_installment_payments (
        id INTEGER PRIMARY KEY,
        payroll_run_id INTEGER,
        employee_id INTEGER,
        loan_id INTEGER,
        installment_id INTEGER,
        installment_no INTEGER,
        deduction_name VARCHAR(255),
        amount NUMERIC(14,2),
        remaining_balance NUMERIC(14,2),
        is_final_installment BOOLEAN,
        proc_year INTEGER,
        proc_month INTEGER,
        proc_half INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_payroll_salary_retrieve (
        id INTEGER PRIMARY KEY,
        payroll_run_id INTEGER,
        employee_id INTEGER,
        is_bank BOOLEAN,
        proc_year INTEGER,
        proc_month INTEGER,
        proc_half INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_payroll_salary_bank_data (
        id INTEGER PRIMARY KEY,
        ref_retrieve_id INTEGER,
        bank_id INTEGER,
        bank_branch_id INTEGER,
        bank_acc_no VARCHAR(128),
        bank_amount NUMERIC(14,2),
        bank_passbook_name VARCHAR(255),
        is_primary_account BOOLEAN,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_payroll_bank (
        id INTEGER PRIMARY KEY,
        bank_code VARCHAR(32),
        bank_name VARCHAR(255),
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_payroll_bank_branch (
        id INTEGER PRIMARY KEY,
        ref_bank_id INTEGER,
        branch_code VARCHAR(32),
        branch_name VARCHAR(255),
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_payroll_compliance_basic (
        id INTEGER PRIMARY KEY,
        payroll_run_id INTEGER,
        employee_id INTEGER,
        compliance_salary NUMERIC(14,2),
        compliance_ot NUMERIC(14,2),
        compliance_nopay NUMERIC(14,2),
        compliance_attendance_days NUMERIC(14,2),
        compliance_work_hours NUMERIC(14,2),
        compliance_status VARCHAR(64),
        proc_year INTEGER,
        proc_month INTEGER,
        proc_half INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_payroll_compliance_attendance (
        id INTEGER PRIMARY KEY,
        payroll_run_id INTEGER,
        employee_id INTEGER,
        attendance_item_type VARCHAR(64),
        attendance_days NUMERIC(14,2),
        payable_days NUMERIC(14,2),
        absent_days NUMERIC(14,2),
        late_days NUMERIC(14,2),
        nopay_days NUMERIC(14,2),
        ot_hours NUMERIC(14,2),
        attendance_amount NUMERIC(14,2),
        attendance_deduction NUMERIC(14,2),
        proc_year INTEGER,
        proc_month INTEGER,
        proc_half INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_payroll_multi_currency (
        id INTEGER PRIMARY KEY,
        payroll_run_id INTEGER,
        employee_id INTEGER,
        source_currency VARCHAR(16),
        target_currency VARCHAR(16),
        exchange_rate NUMERIC(14,6),
        salary_amount NUMERIC(14,2),
        converted_amount NUMERIC(14,2),
        proc_year INTEGER,
        proc_month INTEGER,
        proc_half INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_payroll_noncash_benefits (
        id INTEGER PRIMARY KEY,
        payroll_run_id INTEGER,
        employee_id INTEGER,
        benefit_name VARCHAR(255),
        benefit_type VARCHAR(64),
        benefit_value NUMERIC(14,2),
        taxable_value NUMERIC(14,2),
        proc_year INTEGER,
        proc_month INTEGER,
        proc_half INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_payroll_non_consider_items (
        id INTEGER PRIMARY KEY,
        payroll_run_id INTEGER,
        employee_id INTEGER,
        item_name VARCHAR(255),
        amount NUMERIC(14,2),
        is_considered_for_payroll BOOLEAN,
        proc_year INTEGER,
        proc_month INTEGER,
        proc_half INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_payroll_salary_analyze (
        id INTEGER PRIMARY KEY,
        payroll_group_id INTEGER,
        proc_year INTEGER,
        proc_month INTEGER,
        proc_half INTEGER DEFAULT 0,
        process_start_time TIMESTAMPTZ,
        process_end_time TIMESTAMPTZ,
        processed_employee_count INTEGER,
        failed_employee_count INTEGER,
        reversed_employee_count INTEGER,
        process_type VARCHAR(64),
        process_status VARCHAR(64),
        triggered_by VARCHAR(255),
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_prl_loan (
        id INTEGER PRIMARY KEY,
        employee_id INTEGER,
        loan_type_name VARCHAR(255),
        loan_amount NUMERIC(14,2),
        loan_balance NUMERIC(14,2),
        is_active BOOLEAN,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_payroll_salary_analyze_data (
        id INTEGER PRIMARY KEY,
        analyze_id INTEGER,
        employee_id INTEGER,
        line_amount NUMERIC(14,2),
        line_name VARCHAR(255),
        proc_year INTEGER,
        proc_month INTEGER,
        proc_half INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".raw_hr_payroll_groups (
        id INTEGER PRIMARY KEY,
        payroll_group_name VARCHAR(255),
        legal_entity_id INTEGER,
        currency_code VARCHAR(16),
        payroll_frequency VARCHAR(64),
        is_active BOOLEAN,
        is_available_epf8 BOOLEAN,
        is_available_epf12 BOOLEAN,
        is_available_etf3 BOOLEAN,
        is_available_tax BOOLEAN,
        is_stamp_duty BOOLEAN,
        pg_registered_name VARCHAR(250),
        pg_epf_employer_no VARCHAR(10),
        consider_ot_for_payroll BOOLEAN,
        consider_late_for_payroll BOOLEAN,
        consider_nopay_for_payroll BOOLEAN,
        pg_is_multicycle BOOLEAN,
        pg_cycles_per_month INTEGER,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_performance_reviews (
        id INTEGER PRIMARY KEY,
        employee_id INTEGER,
        reviewer_id INTEGER,
        review_period VARCHAR(32),
        review_year INTEGER,
        overall_score NUMERIC(6,2),
        rating VARCHAR(64),
        status VARCHAR(64),
        review_date DATE,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_training_records (
        id INTEGER PRIMARY KEY,
        employee_id INTEGER,
        training_id INTEGER,
        training_name VARCHAR(255),
        training_type VARCHAR(64),
        start_date DATE,
        end_date DATE,
        status VARCHAR(64),
        score NUMERIC(6,2),
        cost NUMERIC(14,2),
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS "{schema}".stg_lifecycle (
        id INTEGER PRIMARY KEY,
        employee_id INTEGER NOT NULL,
        lifecycle_position INTEGER,
        position_name VARCHAR(255),
        effective_date TIMESTAMPTZ,
        previous_designation VARCHAR(255),
        new_designation VARCHAR(255),
        previous_grade VARCHAR(255),
        new_grade VARCHAR(255),
        previous_location VARCHAR(255),
        new_location VARCHAR(255),
        new_legal_entity VARCHAR(255),
        new_company_section VARCHAR(255),
        new_section VARCHAR(255),
        previous_section VARCHAR(255),
        new_salary NUMERIC(14,2),
        previous_salary NUMERIC(14,2),
        reason TEXT,
        triggered_by_emp_id INTEGER,
        approval_date TIMESTAMPTZ,
        approved_date_time TIMESTAMPTZ,
        resignation_approved_date DATE,
        last_working_date DATE,
        parent_lifecycle_id INTEGER,
        approval_status INTEGER,
        created_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ,
        extracted_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,
]

# Backfill columns on existing staging tables (CREATE IF NOT EXISTS does not add columns).
STAGING_ALTER_DDL: list[str] = [
    'ALTER TABLE "{schema}".stg_employees ADD COLUMN IF NOT EXISTS legal_entity_id INTEGER',
    'ALTER TABLE "{schema}".stg_employees ADD COLUMN IF NOT EXISTS legal_entity_name VARCHAR(255)',
    'ALTER TABLE "{schema}".stg_employees ADD COLUMN IF NOT EXISTS legal_entity_code VARCHAR(64)',
    'ALTER TABLE "{schema}".stg_employees ADD COLUMN IF NOT EXISTS designation_name VARCHAR(255)',
    'ALTER TABLE "{schema}".stg_employees ADD COLUMN IF NOT EXISTS designation_department VARCHAR(255)',
    'ALTER TABLE "{schema}".stg_employees ADD COLUMN IF NOT EXISTS grade_name VARCHAR(64)',
    'ALTER TABLE "{schema}".stg_employees ADD COLUMN IF NOT EXISTS employee_category VARCHAR(128)',
    'ALTER TABLE "{schema}".stg_employees ADD COLUMN IF NOT EXISTS employee_category_code VARCHAR(64)',
    'ALTER TABLE "{schema}".stg_employees ADD COLUMN IF NOT EXISTS location_name VARCHAR(255)',
    'ALTER TABLE "{schema}".stg_employees ADD COLUMN IF NOT EXISTS basic_salary NUMERIC(14, 2)',
    'ALTER TABLE "{schema}".stg_employees ADD COLUMN IF NOT EXISTS epf_no VARCHAR(64)',
    'ALTER TABLE "{schema}".raw_hr_payroll_groups ADD COLUMN IF NOT EXISTS is_available_epf8 BOOLEAN',
    'ALTER TABLE "{schema}".raw_hr_payroll_groups ADD COLUMN IF NOT EXISTS is_available_epf12 BOOLEAN',
    'ALTER TABLE "{schema}".raw_hr_payroll_groups ADD COLUMN IF NOT EXISTS is_available_etf3 BOOLEAN',
    'ALTER TABLE "{schema}".raw_hr_payroll_groups ADD COLUMN IF NOT EXISTS is_available_tax BOOLEAN',
    'ALTER TABLE "{schema}".raw_hr_payroll_groups ADD COLUMN IF NOT EXISTS is_stamp_duty BOOLEAN',
    'ALTER TABLE "{schema}".raw_hr_payroll_groups ADD COLUMN IF NOT EXISTS pg_registered_name VARCHAR(250)',
    'ALTER TABLE "{schema}".raw_hr_payroll_groups ADD COLUMN IF NOT EXISTS pg_epf_employer_no VARCHAR(10)',
    'ALTER TABLE "{schema}".raw_hr_payroll_groups ADD COLUMN IF NOT EXISTS consider_ot_for_payroll BOOLEAN',
    'ALTER TABLE "{schema}".raw_hr_payroll_groups ADD COLUMN IF NOT EXISTS consider_late_for_payroll BOOLEAN',
    'ALTER TABLE "{schema}".raw_hr_payroll_groups ADD COLUMN IF NOT EXISTS consider_nopay_for_payroll BOOLEAN',
    'ALTER TABLE "{schema}".raw_hr_payroll_groups ADD COLUMN IF NOT EXISTS pg_is_multicycle BOOLEAN',
    'ALTER TABLE "{schema}".raw_hr_payroll_groups ADD COLUMN IF NOT EXISTS pg_cycles_per_month INTEGER',
    'ALTER TABLE "{schema}".stg_payroll_runs ADD COLUMN IF NOT EXISTS payroll_half INTEGER DEFAULT 0',
    'ALTER TABLE "{schema}".stg_payroll_details ADD COLUMN IF NOT EXISTS processing_half INTEGER DEFAULT 0',
    'ALTER TABLE "{schema}".stg_payroll_details ADD COLUMN IF NOT EXISTS ref_fortnight_id INTEGER',
    'ALTER TABLE "{schema}".stg_payroll_details ADD COLUMN IF NOT EXISTS epf_employee_amount NUMERIC(14, 2)',
    'ALTER TABLE "{schema}".stg_payroll_details ADD COLUMN IF NOT EXISTS epf_employer_amount NUMERIC(14, 2)',
    'ALTER TABLE "{schema}".stg_payroll_details ADD COLUMN IF NOT EXISTS etf_amount NUMERIC(14, 2)',
    'ALTER TABLE "{schema}".stg_payroll_details ADD COLUMN IF NOT EXISTS pay_cut_amount NUMERIC(14, 2)',
    'ALTER TABLE "{schema}".stg_payroll_details ADD COLUMN IF NOT EXISTS increment_amount NUMERIC(14, 2)',
    'ALTER TABLE "{schema}".stg_payroll_add_ded ADD COLUMN IF NOT EXISTS proc_half INTEGER DEFAULT 0',
    'ALTER TABLE "{schema}".stg_payroll_attendance_lines ADD COLUMN IF NOT EXISTS proc_half INTEGER DEFAULT 0',
    'ALTER TABLE "{schema}".stg_payroll_variable_additions ADD COLUMN IF NOT EXISTS proc_half INTEGER DEFAULT 0',
    'ALTER TABLE "{schema}".stg_payroll_variable_deductions ADD COLUMN IF NOT EXISTS proc_half INTEGER DEFAULT 0',
    'ALTER TABLE "{schema}".stg_payroll_details ADD COLUMN IF NOT EXISTS ot_amount NUMERIC(14, 2)',
    'ALTER TABLE "{schema}".stg_payroll_details ADD COLUMN IF NOT EXISTS bonus_amount NUMERIC(14, 2)',
    'ALTER TABLE "{schema}".stg_payroll_details ADD COLUMN IF NOT EXISTS attendance_deduction NUMERIC(14, 2)',
    'ALTER TABLE "{schema}".stg_payroll_details ADD COLUMN IF NOT EXISTS nopay_deduction NUMERIC(14, 2)',
    'ALTER TABLE "{schema}".stg_payroll_details ADD COLUMN IF NOT EXISTS loan_deduction NUMERIC(14, 2)',
    'ALTER TABLE "{schema}".stg_payroll_details ADD COLUMN IF NOT EXISTS installment_deduction NUMERIC(14, 2)',
    'ALTER TABLE "{schema}".stg_payroll_details ADD COLUMN IF NOT EXISTS service_charge NUMERIC(14, 2)',
    'ALTER TABLE "{schema}".stg_payroll_details ADD COLUMN IF NOT EXISTS currency_code VARCHAR(16)',
    'ALTER TABLE "{schema}".stg_payroll_details ADD COLUMN IF NOT EXISTS exchange_rate NUMERIC(14, 6)',
    'ALTER TABLE "{schema}".stg_payroll_details ADD COLUMN IF NOT EXISTS is_multi_currency BOOLEAN',
    'ALTER TABLE "{schema}".stg_payroll_details ADD COLUMN IF NOT EXISTS is_compliance_processed BOOLEAN',
    'ALTER TABLE "{schema}".stg_payroll_details ADD COLUMN IF NOT EXISTS process_status VARCHAR(64)',
    'ALTER TABLE "{schema}".stg_payroll_details ADD COLUMN IF NOT EXISTS original_process_reference INTEGER',
    'ALTER TABLE "{schema}".stg_payroll_details ADD COLUMN IF NOT EXISTS reversal_timestamp TIMESTAMPTZ',
    'ALTER TABLE "{schema}".stg_payroll_details ADD COLUMN IF NOT EXISTS reversed_by INTEGER',
    'ALTER TABLE "{schema}".stg_payroll_details ADD COLUMN IF NOT EXISTS reversal_reason VARCHAR(255)',
    'ALTER TABLE "{schema}".stg_payroll_tax ADD COLUMN IF NOT EXISTS tax_relief_amount NUMERIC(14, 2)',
    'ALTER TABLE "{schema}".stg_payroll_tax ADD COLUMN IF NOT EXISTS tax_percentage NUMERIC(8, 4)',
    'ALTER TABLE "{schema}".stg_payroll_tax ADD COLUMN IF NOT EXISTS annualized_taxable_income NUMERIC(14, 2)',
    'ALTER TABLE "{schema}".stg_payroll_salary_retrieve ADD COLUMN IF NOT EXISTS payroll_run_id INTEGER',
    'ALTER TABLE "{schema}".stg_payroll_salary_retrieve ADD COLUMN IF NOT EXISTS employee_id INTEGER',
    'ALTER TABLE "{schema}".stg_payroll_salary_retrieve ADD COLUMN IF NOT EXISTS is_bank BOOLEAN',
    'ALTER TABLE "{schema}".stg_payroll_salary_retrieve ADD COLUMN IF NOT EXISTS proc_year INTEGER',
    'ALTER TABLE "{schema}".stg_payroll_salary_retrieve ADD COLUMN IF NOT EXISTS proc_month INTEGER',
    'ALTER TABLE "{schema}".stg_payroll_salary_retrieve ADD COLUMN IF NOT EXISTS proc_half INTEGER DEFAULT 0',
    'ALTER TABLE "{schema}".stg_payroll_salary_bank_data ADD COLUMN IF NOT EXISTS ref_retrieve_id INTEGER',
    'ALTER TABLE "{schema}".stg_payroll_salary_bank_data ADD COLUMN IF NOT EXISTS bank_id INTEGER',
    'ALTER TABLE "{schema}".stg_payroll_salary_bank_data ADD COLUMN IF NOT EXISTS bank_branch_id INTEGER',
    'ALTER TABLE "{schema}".stg_payroll_salary_bank_data ADD COLUMN IF NOT EXISTS bank_acc_no VARCHAR(128)',
    'ALTER TABLE "{schema}".stg_payroll_salary_bank_data ADD COLUMN IF NOT EXISTS bank_amount NUMERIC(14, 2)',
    'ALTER TABLE "{schema}".stg_payroll_salary_bank_data ADD COLUMN IF NOT EXISTS bank_passbook_name VARCHAR(255)',
    'ALTER TABLE "{schema}".stg_payroll_salary_bank_data ADD COLUMN IF NOT EXISTS is_primary_account BOOLEAN',
    'ALTER TABLE "{schema}".stg_payroll_bank ADD COLUMN IF NOT EXISTS bank_code VARCHAR(32)',
    'ALTER TABLE "{schema}".stg_payroll_bank ADD COLUMN IF NOT EXISTS bank_name VARCHAR(255)',
    'ALTER TABLE "{schema}".stg_payroll_bank_branch ADD COLUMN IF NOT EXISTS ref_bank_id INTEGER',
    'ALTER TABLE "{schema}".stg_payroll_bank_branch ADD COLUMN IF NOT EXISTS branch_code VARCHAR(32)',
    'ALTER TABLE "{schema}".stg_payroll_bank_branch ADD COLUMN IF NOT EXISTS branch_name VARCHAR(255)',
    'ALTER TABLE "{schema}".stg_leave_types ADD COLUMN IF NOT EXISTS requires_coverup BOOLEAN',
    'ALTER TABLE "{schema}".stg_leave_types ADD COLUMN IF NOT EXISTS allow_attachment BOOLEAN',
    'ALTER TABLE "{schema}".stg_leave_types ADD COLUMN IF NOT EXISTS attachment_mandatory BOOLEAN',
    'ALTER TABLE "{schema}".stg_leave_types ADD COLUMN IF NOT EXISTS requires_approval BOOLEAN',
    'ALTER TABLE "{schema}".stg_leave_types ADD COLUMN IF NOT EXISTS allow_half_day BOOLEAN',
    'ALTER TABLE "{schema}".stg_leave_types ADD COLUMN IF NOT EXISTS entitlement_based BOOLEAN',
    'ALTER TABLE "{schema}".stg_leave_requests ADD COLUMN IF NOT EXISTS status_code INTEGER',
    'ALTER TABLE "{schema}".stg_leave_requests ADD COLUMN IF NOT EXISTS final_status_code INTEGER',
    'ALTER TABLE "{schema}".stg_leave_requests ADD COLUMN IF NOT EXISTS purpose_id INTEGER',
    'ALTER TABLE "{schema}".stg_leave_requests ADD COLUMN IF NOT EXISTS is_hr_approval BOOLEAN',
    'ALTER TABLE "{schema}".stg_leave_requests ADD COLUMN IF NOT EXISTS request_date TIMESTAMPTZ',
    'ALTER TABLE "{schema}".stg_leave_requests ADD COLUMN IF NOT EXISTS approval_date TIMESTAMPTZ',
    'ALTER TABLE "{schema}".stg_lieu_leave_entitlement ADD COLUMN IF NOT EXISTS calendar_date DATE',
]
