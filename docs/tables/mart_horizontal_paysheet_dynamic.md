# mart_horizontal_paysheet_dynamic

## Overview

**Business Purpose:**  
Wide paysheet with one column per distinct add/ded/variable item.

**Schema:** `hr`  
**Object Type:** Table  
**Layer:** Mart  
**Domain:** Payroll  
**Grain:** Pivoted pay items  
**Primary Key:** TBD  
**Business Key:** emp_no  
**SCD Type:** N/A  
**Refresh Type:** Batch  
**Refresh Frequency:** Daily  

**Source Systems:**
- TBD

**Consumers:**
- Semantic Views
- Reports
- AI Agent

## Governance

| Property | Value |
|----------|-------|
| Data Owner | Payroll |
| Technical Owner | Data Engineering |
| Classification | Internal |
| Contains PII | No |
| Retention | 7 years |

## Columns

| Column | Type | Nullable | Default | Description | Source | Transformation | PII | Sensitive | AI Aliases |
|--------|------|----------|---------|-------------|--------|----------------|-----|-----------|------------|
| `tenant_id` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `employee_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_period_sk` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `emp_no` | varchar(64) | Yes | - | TBD | TBD | TBD | No | No | employee number, employee code, staff id |
| `emp_fullname` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | employee name, full name, staff name |
| `designation` | text | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `branch` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_group_name` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_year` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_month` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_half` | integer | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `basic_salary` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `gross_salary` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | gross pay, gross earnings |
| `net_salary` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | net pay, take home pay |
| `total_allowance` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `total_deduction` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `ot_amount` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `bonus_amount` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `tax_amount` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `epf_employee` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `epf_employer` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `etf_amount` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `nopay_amount` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `loan_deduction` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `pay_cut_amount` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `increment_amount` | numeric(14,2) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `payroll_currency` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `process_status` | varchar(255) | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `addition_addition_1` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `addition_addition_2` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `addition_annual_leave_encashment` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `addition_blend_allowance` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `addition_car_allowance` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `addition_component_10` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `addition_component_2` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `addition_component_4` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `addition_component_8` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `addition_component_9` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `addition_cricket_allowance` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `addition_dollar_pegged` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `addition_earn_leave_encashment` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `addition_fuel_transport_allowance` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `addition_inflation_allowance` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `addition_inflation_allowance_arrears` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `addition_night_allowance` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `addition_ot_arrears` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `addition_over_time_1_5` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `addition_parent_and_child_benefit` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `addition_poya_day_wage` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `addition_salary_arrears` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `addition_sales_incentive` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `addition_sunday_wage` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deduction_blend_allowance_recovery` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deduction_component_10` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deduction_component_11` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deduction_component_12` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deduction_component_13` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deduction_component_3` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deduction_component_4` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deduction_component_5` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deduction_component_7` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deduction_component_8` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deduction_component_9` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deduction_dollar_pegged_recovery` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deduction_fuel_or_transport_recovery` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deduction_inflation_allowance_recovery` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deduction_loan` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deduction_loan_without_interest` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deduction_no_pay_deduction` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deduction_over_time_recovery` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `deduction_salary_advance` | numeric | Yes | - | TBD | TBD | TBD | No | Yes | TBD |
| `deduction_sales_incentive_recovery` | numeric | Yes | - | TBD | TBD | TBD | No | No | TBD |
| `_refreshed_at` | timestamp | Yes | - | TBD | TBD | TBD | No | No | TBD |
