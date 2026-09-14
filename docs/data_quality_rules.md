# Data Quality Rules

Validation rules for warehouse objects (dbt tests + design rules).

## Employee surrogate key uniqueness

**Scope:** `dim_employee`  
**Validation:** `COUNT(DISTINCT employee_sk) = COUNT(*) on dim_employee versions`  

## One current employee version

**Scope:** `dim_employee`  
**Validation:** `At most one is_current = true per tenant_id, source_system, source_emp_id`  

## No future birth dates

**Scope:** `dim_employee`  
**Validation:** `date_of_birth <= CURRENT_DATE OR date_of_birth IS NULL`  

## Leave end date after start date

**Scope:** `fct_leave_application`  
**Validation:** `end_date >= start_date`  

## Leave days non-negative

**Scope:** `fct_leave_application`  
**Validation:** `requested_days >= 0 AND approved_days >= 0`  

## Processed salary grain uniqueness

**Scope:** `fct_processed_salary`  
**Validation:** `UNIQUE(tenant_id, source_system, source_processed_salary_id)`  

## Payroll net not greater than gross

**Scope:** `fct_processed_salary`  
**Validation:** `net_salary <= gross_salary (flag exceptions)`  
