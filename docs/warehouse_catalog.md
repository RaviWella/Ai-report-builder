# Warehouse Catalog

MintHRM Enterprise Data Warehouse — object inventory.

**Generated:** 2026-06-02 08:46 UTC  
**Owner:** Data Engineering  

| Object | Schema | Type | Domain | Layer | Refresh | Description |
|--------|--------|------|--------|-------|---------|-------------|
| `dim_bank` | `hr` | Table | Payroll | Dimension | Daily | Payroll bank dimension. |
| `dim_bank_branch` | `hr` | Table | Payroll | Dimension | Daily | Payroll bank branch dimension. |
| `dim_canonical_pay_item` | `hr` | Table | Payroll | Dimension | Daily | Canonical mapping for dynamic payroll line labels (seed-driven; API extensible). |
| `dim_canonical_pay_item_seed` | `hr` | Table | Payroll | Dimension | Daily | TBD |
| `dim_date` | `hr` | Table | Workforce | Dimension | Daily | Calendar dimension — day grain; month-start dates link to snapshot_month. |
| `dim_designation` | `hr` | Table | Workforce | Dimension | Daily | SCD Type 2 job title dimension from snap_designation. |
| `dim_employee` | `hr` | Table | Workforce | Dimension | Daily | SCD Type 2 employee dimension. One row per (tenant_id, source_emp_id, version). Built on snap_employee. Every fact table |
| `dim_leave_approval_level` | `hr` | Table | Leave Management | Dimension | Daily | Approval hierarchy lookup. |
| `dim_leave_reason` | `hr` | Table | Leave Management | Dimension | Daily | Predefined leave purpose lookup. |
| `dim_leave_source` | `hr` | Table | Leave Management | Dimension | Daily | Leave module origin lookup. |
| `dim_leave_status` | `hr` | Table | Leave Management | Dimension | Daily | Normalized leave workflow status lookup. |
| `dim_leave_type` | `hr` | Table | Leave Management | Dimension | Daily | SCD2 leave type dimension (hr_leavetype). |
| `dim_org_unit` | `hr` | Table | Workforce | Dimension | Daily | Org hierarchy dimension from company_hierarchy / stg_departments. |
| `dim_payroll_group` | `hr` | Table | Payroll | Dimension | Daily | Payroll processing group dimension (from hr_payroll_groups). |
| `dim_payroll_period` | `hr` | Table | Payroll | Dimension | Daily | Payroll calendar dimension (year × month × half). |
| `dim_shift` | `hr` | Table | Attendance | Dimension | Daily | SCD Type 2 shift dimension from snap_shift. |
| `fact_attendance` | `hr` | Table | Attendance | Fact | Daily | Daily attendance fact — one row per employee per day. |
| `fact_leave_balance` | `hr` | Table | Leave Management | Fact | Daily | Legacy leave balance view — approved applications from fct_leave_application. |
| `fact_payroll` | `hr` | View | Payroll | Fact | Daily | Legacy payroll view — refs fct_processed_salary (Phase 6). |
| `fct_compliance_payroll` | `hr` | Table | Payroll | Fact | Daily | EPF/ETF compliance amounts from processed salary statutory columns. |
| `fct_daily_attendance` | `hr` | Table | Attendance | Fact | Daily | Daily attendance fact (emp × shift_day × shift_order). Incremental delete+insert. |
| `fct_employment_snapshot` | `hr` | Table | Workforce | Fact | Daily | Monthly employment state at month-end with FKs to dim_employee, dim_designation (PIT), and dim_org_unit. |
| `fct_leave_application` | `hr` | Table | Leave Management | Fact | Daily | One row per leave application (Phase 1 standard leave). |
| `fct_leave_approval` | `hr` | Table | Leave Management | Fact | Daily | One row per leave approval action. |
| `fct_leave_balance_snapshot` | `hr` | Table | Leave Management | Fact | Daily | Employee x leave type x snapshot date balance. |
| `fct_leave_daily` | `hr` | Table | Leave Management | Fact | Daily | One row per employee per leave date. |
| `fct_leave_planner` | `hr` | Table | Leave Management | Fact | Daily | One row per planned leave. |
| `fct_lieu_leave_entitlement` | `hr` | Table | Leave Management | Fact | Daily | Earned lieu leave entitlement event. |
| `fct_lifecycle_event` | `hr` | Table | Workforce | Fact | Daily | Career lifecycle fact (one row per event). PIT join to dim_employee on effective_date. |
| `fct_maternity_leave` | `hr` | Table | Leave Management | Fact | Daily | One row per maternity leave request. |
| `fct_noncash_benefit` | `hr` | Table | Enterprise HR | Fact | Daily | TBD |
| `fct_overtime` | `hr` | Table | Attendance | Fact | Daily | Overtime fact per employee × day (derived from attendance until prl_overtime is staged). |
| `fct_payroll_process_execution` | `hr` | Table | Payroll | Fact | Daily | Payroll run execution metadata (from stg_payroll_runs / processed snapshots). |
| `fct_processed_add_ded` | `hr` | Table | Enterprise HR | Fact | Daily | Vertical additions/deductions fact from processed_sal_add_ded. |
| `fct_processed_attendance_payroll` | `hr` | Table | Payroll | Fact | Daily | TBD |
| `fct_processed_loan_deduction` | `hr` | Table | Payroll | Fact | Daily | Loan and installment deductions from processed_loan_data / installments. |
| `fct_processed_multi_currency_salary` | `hr` | Table | Payroll | Fact | Daily | TBD |
| `fct_processed_salary` | `hr` | Table | Payroll | Fact | Daily | Processed payroll snapshot fact. Grain: employee_sk × payroll_period_sk × payroll_group_sk. |
| `fct_processed_tax` | `hr` | Table | Payroll | Fact | Daily | Processed tax breakdown per employee × period × tax component. |
| `fct_salary_bank_instruction` | `hr` | Table | Payroll | Fact | Daily | Bank payment instructions by employee × payroll period. |
| `fct_salary_change` | `hr` | Table | Payroll | Fact | Daily | Salary revision fact from hr_lifecycle pay-change rows. PIT join to dim_employee. |
| `fct_short_leave_usage` | `hr` | Table | Leave Management | Fact | Daily | One row per short leave request. |
| `fct_variable_pay_item` | `hr` | Table | Enterprise HR | Fact | Daily | Dynamic variable additions/deductions fact. |
| `mart_attendance_monthly_summary` | `hr` | Table | Attendance | Mart | Daily | Monthly per-employee attendance and OT rollups for BI dashboards. |
| `mart_cost_to_company` | `hr` | Table | Payroll | Mart | Daily | TBD |
| `mart_department_leave_heatmap` | `hr` | Table | Leave Management | Mart | Daily | Department x calendar date absence heatmap. |
| `mart_dynamic_pay_items` | `hr` | Table | Enterprise HR | Mart | Daily | TBD |
| `mart_employee_current` | `hr` | Table | Enterprise HR | Mart | Daily | Denormalized current-state OBT for active employees only. Computed age, tenure, probation flags. The thing BI dashboards |
| `mart_headcount_monthly` | `hr` | Table | Workforce | Mart | Daily | Monthly tenant-level workforce snapshot from fct_employment_snapshot. Headcount and status splits are month-end (EOM) po |
| `mart_horizontal_paysheet_core` | `hr` | Table | Payroll | Mart | Daily | Paysheet core columns per employee × period. |
| `mart_horizontal_paysheet_dynamic` | `hr` | Table | Payroll | Mart | Daily | Wide paysheet with one column per distinct add/ded/variable item. |
| `mart_leave_employee_profile` | `hr` | Table | Leave Management | Mart | Daily | Employee leave behavior profile. |
| `mart_leave_monthly_summary` | `hr` | Table | Leave Management | Mart | Daily | Month x department x leave type rollup. |
| `mart_payroll_pivot_column_catalog` | `hr` | Table | Payroll | Mart | Daily | Discovered dynamic paysheet column catalog per tenant. |
| `mart_payroll_reconciliation` | `hr` | Table | Payroll | Mart | Daily | TBD |
| `mart_processed_payroll_summary` | `hr` | Table | Payroll | Mart | Daily | Primary payroll BI mart per employee × period (§8.1). |
| `mart_salary_band_summary` | `hr` | Table | Payroll | Mart | Daily | Current compensation bands by legal entity, designation, and grade (active employees). |
| `mart_statutory_summary` | `hr` | Table | Payroll | Mart | Daily | TBD |
| `payroll_report_column_config` | `hr` | Table | Payroll | Other | Daily | TBD |
| `vw_attendance_summary` | `hr_semantic` | View | Attendance | Semantic | Daily | Semantic API view over mart_attendance_monthly_summary. |
| `vw_current_leave_balance` | `hr_semantic` | View | Leave Management | Semantic | Daily | Semantic API view over fct_leave_balance_snapshot, dim_employee, dim_leave_type. |
| `vw_data_dictionary` | `hr_semantic` | View | Enterprise HR | Semantic | Daily | Semantic consumer view (stable API over physical marts). |
| `vw_employee_leave_history` | `hr_semantic` | View | Leave Management | Semantic | Daily | Semantic API view over fct_leave_application, dim_employee, dim_leave_type. |
| `vw_employment_monthly` | `hr_semantic` | View | Workforce | Semantic | Daily | Semantic API view over fct_employment_snapshot. |
| `vw_headcount` | `hr_semantic` | View | Workforce | Semantic | Daily | Semantic API view over mart_headcount_monthly, dim_employee. |
| `vw_leave_liability` | `hr_semantic` | View | Leave Management | Semantic | Daily | Semantic API view over fct_leave_balance_snapshot, dim_employee, dim_leave_type. |
| `vw_leave_summary` | `hr_semantic` | View | Leave Management | Semantic | Daily | Semantic API view over fact_leave_balance, fct_leave_application, dim_employee. |
| `vw_leave_utilization` | `hr_semantic` | View | Leave Management | Semantic | Daily | Semantic API view over mart_leave_monthly_summary, fct_leave_balance_snapshot. |
| `vw_lifecycle_summary` | `hr_semantic` | View | Workforce | Semantic | Daily | Semantic API view over fct_lifecycle_event. |
| `vw_payroll_summary` | `hr_semantic` | View | Payroll | Semantic | Daily | Semantic API view over mart_processed_payroll_summary, payroll facts. |
| `vw_pending_leave_approvals` | `hr_semantic` | View | Leave Management | Semantic | Daily | Semantic API view over fct_leave_approval, fct_leave_application, dim_employee. |
| `vw_performance_summary` | `hr_semantic` | View | Enterprise HR | Semantic | Daily | Semantic API view over performance staging. |
| `vw_salary_bands` | `hr_semantic` | View | Payroll | Semantic | Daily | Semantic API view over mart_salary_band_summary. |
| `vw_turnover` | `hr_semantic` | View | Workforce | Semantic | Daily | Semantic API view over lifecycle / employment facts. |
| `snap_designation` | `hr_snap` | Table | Enterprise HR | Snapshot | Daily | dbt snapshot history for dim_designation (feeds warehouse SCD2 dimensions). |
| `snap_employee` | `hr_snap` | Table | Enterprise HR | Snapshot | Daily | dbt snapshot history for dim_employee (feeds warehouse SCD2 dimensions). |
| `snap_leave_type` | `hr_snap` | Table | Leave Management | Snapshot | Daily | dbt snapshot history for dim_leave_type (feeds warehouse SCD2 dimensions). |
| `snap_shift` | `hr_snap` | Table | Attendance | Snapshot | Daily | dbt snapshot history for dim_shift (feeds warehouse SCD2 dimensions). |
| `raw_events` | `hr_raw` | Table | Enterprise HR | Staging | Daily | Raw event landing (source_table identifies originating MintHRM entity). |
| `raw_hr_payroll_groups` | `hr_raw` | Table | Payroll | Staging | Daily | Raw payroll group definitions from hr_payroll_groups. |
| `raw_processed_sal_basic_data` | `hr_raw` | View | Enterprise HR | Staging | Daily | Raw processed salary snapshot landing (feeds stg_payroll_details / stg_processed_sal_basic_data). |
| `stg_attendance` | `hr_raw` | Table | Attendance | Staging | Daily | Daily attendance punches and worked hours from HR_ATTEDANCE. |
| `stg_bank` | `hr_raw` | View | Payroll | Staging | Daily | Bank master (payroll) from MintHRM bank table. |
| `stg_branches` | `hr_raw` | Table | Enterprise HR | Staging | Daily | Branch/location master from MintHRM branch (br_id, br_name). |
| `stg_company_hierarchy_individual` | `hr_raw` | Table | Enterprise HR | Staging | Daily | Per-employee org-chart node; ref_emp_id and parent_id (manager link). |
| `stg_departments` | `hr_raw` | Table | Enterprise HR | Staging | Daily | Organization units from company_hierarchy; fallback distinct departments from VW_MINT_EMP_DEPARTMENT. |
| `stg_designations` | `hr_raw` | Table | Enterprise HR | Staging | Daily | Job titles and grades from hr_designation (desig_id, designation). |
| `stg_employees` | `hr_raw` | Table | Enterprise HR | Staging | Daily | Employee master extract from hr_empbasic with employment and contact enrichment. |
| `stg_hr_payroll_groups` | `hr_raw` | View | Payroll | Staging | Daily | Payroll group master view from hr_payroll_groups. |
| `stg_leave_application_dates` | `hr_raw` | Table | Leave Management | Staging | Daily | Leave day-level breakdown from hr_leaveapplication_dates. |
| `stg_leave_approvals` | `hr_raw` | Table | Leave Management | Staging | Daily | Leave approval workflow actions from hr_leaveapplication_superiors. |
| `stg_leave_balance` | `hr_raw` | Table | Leave Management | Staging | Daily | Leave balance snapshots from hr_leave_balance. |
| `stg_leave_entitlement` | `hr_raw` | Table | Leave Management | Staging | Daily | Leave entitlement rows from prl_leaveentitle. |
| `stg_leave_planner` | `hr_raw` | Table | Leave Management | Staging | Daily | Planned leave from hr_leave_planner (day types in hr_leave_planner_dates). |
| `stg_leave_reason` | `hr_raw` | Table | Leave Management | Staging | Daily | Predefined leave purposes from hr_predefine_leave_purpose. |
| `stg_leave_requests` | `hr_raw` | Table | Leave Management | Staging | Daily | Standard leave applications from hr_leaveapplication. |
| `stg_leave_types` | `hr_raw` | Table | Leave Management | Staging | Daily | Leave type definitions from hr_leavetype. |
| `stg_lieu_leave` | `hr_raw` | Table | Leave Management | Staging | Daily | Lieu (compensatory) leave applications from hr_lieu_leave. |
| `stg_lieu_leave_entitlement` | `hr_raw` | Table | Leave Management | Staging | Daily | Earned lieu-leave entitlements from lieu_leave_entitlement_data. |
| `stg_lifecycle` | `hr_raw` | Table | Workforce | Staging | Daily | Career lifecycle events (hire, transfer, promotion, exit) from hr_lifecycle. |
| `stg_mas_branch` | `hr_raw` | View | Enterprise HR | Staging | Daily | Bank branch master from mas_branch (linked to bank). |
| `stg_maternity_leave` | `hr_raw` | Table | Leave Management | Staging | Daily | Maternity leave applications from hr_leave_maternity. |
| `stg_payroll_add_ded` | `hr_raw` | Table | Payroll | Staging | Daily | Payroll engine extract: processed_sal_add_ded → stg_payroll_add_ded. |
| `stg_payroll_attendance_lines` | `hr_raw` | Table | Payroll | Staging | Daily | Payroll engine extract: processed_sal_attendance → stg_payroll_attendance_lines. |
| `stg_payroll_bank` | `hr_raw` | Table | Payroll | Staging | Daily | Payroll engine extract: bank → stg_payroll_bank. |
| `stg_payroll_bank_branch` | `hr_raw` | Table | Payroll | Staging | Daily | Payroll engine extract: mas_branch → stg_payroll_bank_branch. |
| `stg_payroll_compliance_attendance` | `hr_raw` | Table | Payroll | Staging | Daily | Payroll engine extract: processed_sal_attendance_compliance → stg_payroll_compliance_attendance. |
| `stg_payroll_compliance_basic` | `hr_raw` | Table | Payroll | Staging | Daily | Payroll engine extract: processed_sal_basic_data_compliance → stg_payroll_compliance_basic. |
| `stg_payroll_details` | `hr_raw` | Table | Payroll | Staging | Daily | Payroll engine extract: processed_sal_basic_data → stg_payroll_details. |
| `stg_payroll_installment_payments` | `hr_raw` | Table | Payroll | Staging | Daily | Payroll engine extract: processed_installment_payment_data → stg_payroll_installment_payments. |
| `stg_payroll_loan_data` | `hr_raw` | Table | Payroll | Staging | Daily | Payroll engine extract: processed_loan_data → stg_payroll_loan_data. |
| `stg_payroll_loan_deductions` | `hr_raw` | Table | Payroll | Staging | Daily | Loan and installment deduction lines merged for payroll (processed_loan_data + installments). |
| `stg_payroll_multi_currency` | `hr_raw` | Table | Payroll | Staging | Daily | Payroll engine extract: processed_multi_currency_for_emp_sal → stg_payroll_multi_currency. |
| `stg_payroll_non_consider_items` | `hr_raw` | Table | Payroll | Staging | Daily | Payroll engine extract: processed_non_consider_pay_items → stg_payroll_non_consider_items. |
| `stg_payroll_noncash_benefits` | `hr_raw` | Table | Payroll | Staging | Daily | Payroll engine extract: prl_processed_nonecash_benefits → stg_payroll_noncash_benefits. |
| `stg_payroll_runs` | `hr_raw` | Table | Payroll | Staging | Daily | Payroll run metadata (period x group) aggregated from processed salary snapshots. |
| `stg_payroll_salary_analyze` | `hr_raw` | Table | Payroll | Staging | Daily | Payroll engine extract: prl_processed_salary_analyze → stg_payroll_salary_analyze. |
| `stg_payroll_salary_analyze_data` | `hr_raw` | Table | Payroll | Staging | Daily | Salary analyze detail rows from prl_processed_salary_analyze. |
| `stg_payroll_salary_bank_data` | `hr_raw` | Table | Payroll | Staging | Daily | Payroll engine extract: prl_salary_bank_data → stg_payroll_salary_bank_data. |
| `stg_payroll_salary_retrieve` | `hr_raw` | Table | Payroll | Staging | Daily | Payroll engine extract: prl_salary_retrieve → stg_payroll_salary_retrieve. |
| `stg_payroll_tax` | `hr_raw` | Table | Payroll | Staging | Daily | Payroll engine extract: processed_tax_data_for_employee → stg_payroll_tax. |
| `stg_payroll_variable_additions` | `hr_raw` | Table | Payroll | Staging | Daily | Payroll engine extract: prl_variableadditions_forsal → stg_payroll_variable_additions. |
| `stg_payroll_variable_deductions` | `hr_raw` | Table | Payroll | Staging | Daily | Payroll engine extract: prl_variabledeductions_forsal → stg_payroll_variable_deductions. |
| `stg_performance_reviews` | `hr_raw` | Table | Enterprise HR | Staging | Daily | Performance review staging placeholder until PM source tables are wired in ETL. |
| `stg_prl_loan` | `hr_raw` | Table | Enterprise HR | Staging | Daily | Payroll engine extract: prl_loan → stg_prl_loan. |
| `stg_prl_processed_nonecash_benefits` | `hr_raw` | View | Enterprise HR | Staging | Daily | Processed non-cash benefit lines from prl_processed_nonecash_benefits. |
| `stg_prl_salary_bank_data` | `hr_raw` | View | Payroll | Staging | Daily | Salary bank account split rows from prl_salary_bank_data. |
| `stg_prl_salary_retrieve` | `hr_raw` | View | Payroll | Staging | Daily | Salary retrieve (pay method setup) rows from prl_salary_retrieve. |
| `stg_prl_variable_pay_items` | `hr_raw` | View | Enterprise HR | Staging | Daily | Variable pay additions and deductions staged for dynamic paysheet pivot. |
| `stg_processed_installment_payment_data` | `hr_raw` | View | Enterprise HR | Staging | Daily | Loan installment payment lines from processed_installment_payment_data. |
| `stg_processed_loan_data` | `hr_raw` | View | Enterprise HR | Staging | Daily | Processed loan master rows from processed_loan_data. |
| `stg_processed_loan_deduction` | `hr_raw` | View | Payroll | Staging | Daily | Unified loan deduction staging (loan + installment union for dbt). |
| `stg_processed_multi_currency_for_emp_sal` | `hr_raw` | View | Enterprise HR | Staging | Daily | Multi-currency salary lines from processed_multi_currency_for_emp_sal. |
| `stg_processed_non_consider_pay_items` | `hr_raw` | View | Enterprise HR | Staging | Daily | Non-considered pay items from processed_non_consider_pay_items. |
| `stg_processed_sal_add_ded` | `hr_raw` | View | Enterprise HR | Staging | Daily | Processed add/deduction lines per employee and payroll group. |
| `stg_processed_sal_attendance` | `hr_raw` | View | Attendance | Staging | Daily | Attendance amounts included in processed payroll. |
| `stg_processed_sal_attendance_compliance` | `hr_raw` | View | Payroll | Staging | Daily | Statutory attendance compliance amounts in processed payroll. |
| `stg_processed_sal_basic_data` | `hr_raw` | View | Enterprise HR | Staging | Daily | Normalized processed salary snapshot lines (engine output; lands in stg_payroll_details). |
| `stg_processed_sal_basic_data_compliance` | `hr_raw` | View | Payroll | Staging | Daily | Statutory basic salary compliance slice from payroll engine. |
| `stg_processed_tax_data` | `hr_raw` | View | Payroll | Staging | Daily | Processed tax lines per employee from processed_tax_data_for_employee. |
| `stg_short_leave` | `hr_raw` | Table | Leave Management | Staging | Daily | Short-leave requests from hr_short_leave. |
| `stg_training_records` | `hr_raw` | Table | Enterprise HR | Staging | Daily | Training record staging placeholder until training source tables are mapped in ETL. |
