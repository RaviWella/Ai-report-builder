# Datamart question bank — all final SQL scripts

Total: 66 | With SQL: 66 | Executed: False | Result OK: 0

## [1] advanced_payroll — OK

**Tier:** B | **Source:** verified:bank_advanced_payroll_rank_groups

**Question:**

> For the latest payroll period, rank payroll groups by total net salary and show payroll group name, currency code, employee count, sum of net salary, sum of gross salary, and average basic salary. Exclude groups with zero employees.

**SQL:**

```sql
SELECT
  p.payroll_group_name,
  pg.currency_code,
  COUNT(DISTINCT p.employee_sk) AS employee_count,
  SUM(COALESCE(p.net_salary, 0)) AS total_net_salary,
  SUM(COALESCE(p.gross_salary, 0)) AS total_gross_salary,
  AVG(COALESCE(p.basic_salary, 0)) AS avg_basic_salary
FROM hr_semantic.vw_payroll_summary p
LEFT JOIN hr.dim_payroll_group pg ON pg.payroll_group_name::text = p.payroll_group_name::text
WHERE p.payroll_group_name IS NOT NULL
GROUP BY p.payroll_group_name, pg.currency_code
HAVING COUNT(DISTINCT p.employee_sk) > 0
ORDER BY total_net_salary DESC NULLS LAST
LIMIT 500;
```

---

## [2] advanced_payroll — OK

**Tier:** B | **Source:** verified:bank_advanced_payroll_deduction_ratio

**Question:**

> List employees whose total deductions exceed 25% of gross salary in the latest pay run, including employee name, employee number, branch, payroll group name, gross, total deductions, and net salary. Order by deduction ratio descending.

**SQL:**

```sql
SELECT
  p.emp_fullname AS employee_name,
  p.emp_no AS employee_number,
  p.branch AS branch,
  p.payroll_group_name,
  p.gross_salary,
  p.total_deductions,
  p.net_salary,
  CASE WHEN COALESCE(p.gross_salary, 0) > 0 THEN p.total_deductions / p.gross_salary ELSE NULL END AS deduction_ratio
FROM hr_semantic.vw_payroll_summary p
WHERE COALESCE(p.gross_salary, 0) > 0
  AND p.total_deductions > 0.25 * p.gross_salary
ORDER BY deduction_ratio DESC NULLS LAST
LIMIT 500;
```

---

## [3] advanced_payroll — OK

**Tier:** B | **Source:** verified:bank_advanced_payroll_epf_by_branch

**Question:**

> Compare total EPF employee, ETF, and tax amounts by branch for the current calendar year using processed payroll and tax facts, with branch name from the employee mart.

**SQL:**

```sql
SELECT
  p.branch AS branch_name,
  SUM(COALESCE(p.epf_employee_amount, 0)) AS total_epf_employee,
  SUM(COALESCE(p.etf_amount, 0)) AS total_etf,
  SUM(COALESCE(p.tax_amount, 0)) AS total_tax
FROM hr_semantic.vw_payroll_summary p
WHERE COALESCE(p.payroll_year, EXTRACT(YEAR FROM CURRENT_DATE)::int) = EXTRACT(YEAR FROM CURRENT_DATE)::int
GROUP BY p.branch
ORDER BY total_epf_employee DESC NULLS LAST
LIMIT 500;
```

---

## [4] advanced_payroll — OK

**Tier:** B | **Source:** verified:bank_advanced_payroll_0

**Question:**

> Show month-over-month change in total gross payroll by payroll group for the last six months using processed salary and payroll period dimensions.

**SQL:**

```sql
SELECT
  pg.payroll_group_name,
  date_trunc('month', pp.period_end_date::date) AS pay_month,
  SUM(COALESCE(ps.gross_salary, 0)) AS total_gross
FROM hr.fct_processed_salary ps
JOIN hr.dim_payroll_period pp ON pp.payroll_period_sk = ps.payroll_period_sk
LEFT JOIN hr.dim_payroll_group pg ON pg.payroll_group_sk = ps.payroll_group_sk
WHERE pp.period_end_date >= CURRENT_DATE - INTERVAL '6 months'
GROUP BY 1, 2
ORDER BY pay_month, pg.payroll_group_name
LIMIT 500;
```

---

## [5] advanced_payroll — OK

**Tier:** A | **Source:** payroll_summary_view_template

**Question:**

> Which branches have the highest average basic salary among active employees in the payroll summary view, with at least 5 employees per branch? Include branch, headcount, and average basic salary.

**SQL:**

```sql
SELECT
    v.emp_fullname AS employee_name,
    v.employee_id AS employee_id,
    v.payroll_group_name AS payroll_group_name,
    v.branch AS branch,
    v.basic_salary AS basic_salary,
    pg.payroll_group_name AS payroll_group_name,
    pg.payroll_frequency AS pay_frequency,
    pg.currency_code AS currency_code
FROM hr_semantic.vw_payroll_summary v
LEFT JOIN hr.dim_payroll_group pg
    ON v.payroll_group_name::text = pg.payroll_group_name::text
WHERE v.emp_fullname IS NOT NULL
ORDER BY v.emp_fullname, v.period_label DESC NULLS LAST
LIMIT 500;
```

---

## [6] advanced_payroll — OK

**Tier:** A | **Source:** payroll_summary_view_template

**Question:**

> Prepare a payroll summary report by combining employee, payroll group, and employee snapshot details. Include employee name, employee ID, payroll group name, pay frequency, currency code, branch, and current basic salary for active employees only.

**SQL:**

```sql
SELECT
    v.emp_fullname AS employee_name,
    v.employee_id AS employee_id,
    v.payroll_group_name AS payroll_group_name,
    v.branch AS branch,
    v.basic_salary AS basic_salary,
    pg.payroll_group_name AS payroll_group_name,
    pg.payroll_frequency AS pay_frequency,
    pg.currency_code AS currency_code
FROM hr_semantic.vw_payroll_summary v
LEFT JOIN hr.dim_payroll_group pg
    ON v.payroll_group_name::text = pg.payroll_group_name::text
WHERE v.emp_fullname IS NOT NULL
ORDER BY v.emp_fullname, v.period_label DESC NULLS LAST
LIMIT 500;
```

---

## [7] advanced_leave — OK

**Tier:** B | **Source:** verified:leave_detail_approved

**Question:**

> For each leave type, show total approved leave days, number of distinct employees, and average days per employee this year, using leave balance and current employee branch. Only approved leave.

**SQL:**

```sql
SELECT
  e.emp_fullname AS employee_name,
  e.emp_no AS employee_id,
  e.location_name AS branch,
  lb.leave_type_name AS leave_type,
  lb.period_label AS leave_period,
  lb.days_approved AS total_leave_days,
  lb.balance_days AS balance_remaining
FROM hr.fact_leave_balance lb
JOIN hr.mart_employee_current e ON e.employee_sk = lb.employee_sk
WHERE COALESCE(lb.days_approved, 0) > 0
ORDER BY lb.days_approved DESC
LIMIT 500;
```

---

## [8] advanced_leave — OK

**Tier:** B | **Source:** verified:leave_detail_approved

**Question:**

> List employees who took more than 15 approved leave days in the current year and still have remaining balance below 5 days, with employee name, branch, leave type, days approved, and balance remaining.

**SQL:**

```sql
SELECT
  e.emp_fullname AS employee_name,
  e.emp_no AS employee_id,
  e.location_name AS branch,
  lb.leave_type_name AS leave_type,
  lb.period_label AS leave_period,
  lb.days_approved AS total_leave_days,
  lb.balance_days AS balance_remaining
FROM hr.fact_leave_balance lb
JOIN hr.mart_employee_current e ON e.employee_sk = lb.employee_sk
WHERE COALESCE(lb.days_approved, 0) > 0
ORDER BY lb.days_approved DESC
LIMIT 500;
```

---

## [9] advanced_leave — OK

**Tier:** A | **Source:** leave_balance_template

**Question:**

> Generate a report of employees and their leave details. Include employee name, employee ID, branch, leave type, leave start date, leave end date, total leave days, and leave status. Display only approved leave requests.

**SQL:**

```sql
SELECT
    e.emp_fullname AS employee_name,
    e.emp_no AS employee_id,
    e.location_name AS branch,
    flb.leave_type_name AS leave_type,
    flb.period_label AS leave_start_date,
    flb.period_label AS leave_end_date,
    flb.days_approved AS total_leave_days,
    'approved' AS leave_status
FROM hr.mart_employee_current e
INNER JOIN hr.fact_leave_balance flb
    ON e.employee_sk::text = flb.employee_sk::text
WHERE e.emp_fullname IS NOT NULL
  AND flb.days_approved > 0
ORDER BY flb.period_label DESC NULLS LAST, e.emp_fullname
LIMIT 500;
```

---

## [10] advanced_leave — OK

**Tier:** B | **Source:** verified:leave_detail_approved

**Question:**

> By department, compare total approved leave days versus active headcount and compute average leave days per employee for the current fiscal year.

**SQL:**

```sql
SELECT
  e.emp_fullname AS employee_name,
  e.emp_no AS employee_id,
  e.location_name AS branch,
  lb.leave_type_name AS leave_type,
  lb.period_label AS leave_period,
  lb.days_approved AS total_leave_days,
  lb.balance_days AS balance_remaining
FROM hr.fact_leave_balance lb
JOIN hr.mart_employee_current e ON e.employee_sk = lb.employee_sk
WHERE COALESCE(lb.days_approved, 0) > 0
ORDER BY lb.days_approved DESC
LIMIT 500;
```

---

## [11] advanced_leave — OK

**Tier:** B | **Source:** verified:leave_detail_approved

**Question:**

> Which branches have the highest share of employees with any approved leave in the last 90 days? Show branch, employees on leave, total active employees, and percentage.

**SQL:**

```sql
SELECT
  e.emp_fullname AS employee_name,
  e.emp_no AS employee_id,
  e.location_name AS branch,
  lb.leave_type_name AS leave_type,
  lb.period_label AS leave_period,
  lb.days_approved AS total_leave_days,
  lb.balance_days AS balance_remaining
FROM hr.fact_leave_balance lb
JOIN hr.mart_employee_current e ON e.employee_sk = lb.employee_sk
WHERE COALESCE(lb.days_approved, 0) > 0
ORDER BY lb.days_approved DESC
LIMIT 500;
```

---

## [12] advanced_leave — OK

**Tier:** B | **Source:** verified:leave_detail_approved

**Question:**

> Show employees with consecutive approved leave spans exceeding 10 working days in the current year, including employee name, branch, leave type, start date, end date, and total days.

**SQL:**

```sql
SELECT
  e.emp_fullname AS employee_name,
  e.emp_no AS employee_id,
  e.location_name AS branch,
  lb.leave_type_name AS leave_type,
  lb.period_label AS leave_period,
  lb.days_approved AS total_leave_days,
  lb.balance_days AS balance_remaining
FROM hr.fact_leave_balance lb
JOIN hr.mart_employee_current e ON e.employee_sk = lb.employee_sk
WHERE COALESCE(lb.days_approved, 0) > 0
ORDER BY lb.days_approved DESC
LIMIT 500;
```

---

## [13] advanced_attendance — OK

**Tier:** B | **Source:** verified:bank_advanced_attendance_dept_late

**Question:**

> For this month, rank departments by late arrival events and show present days, absent days, late events, and overtime hours per department from attendance summaries.

**SQL:**

```sql
SELECT
  e.designation_department AS department,
  SUM(COALESCE(ams.days_present, 0)) AS present_days,
  SUM(COALESCE(ams.days_absent, 0)) AS absent_days,
  SUM(COALESCE(ams.days_late, 0)) AS late_events,
  SUM(COALESCE(ams.total_overtime_hours, 0)) AS overtime_hours
FROM hr.mart_attendance_monthly_summary ams
JOIN hr.mart_employee_current e ON e.employee_sk = ams.employee_sk
WHERE ams.year_month = TO_CHAR(CURRENT_DATE, 'YYYY-MM')
GROUP BY e.designation_department
ORDER BY late_events DESC
LIMIT 500;
```

---

## [14] advanced_attendance — OK

**Tier:** B | **Source:** verified:bank_advanced_attendance_1

**Question:**

> List employees with absent days greater than present days in the current month, including employee name, branch, department, absent days, and present days.

**SQL:**

```sql
SELECT
  e.emp_fullname AS employee_name,
  e.location_name AS branch,
  e.designation_department AS department,
  ams.days_absent AS absent_days,
  ams.days_present AS present_days
FROM hr.mart_attendance_monthly_summary ams
JOIN hr.mart_employee_current e ON e.employee_sk = ams.employee_sk
WHERE ams.year_month = TO_CHAR(CURRENT_DATE, 'YYYY-MM')
  AND COALESCE(ams.days_absent, 0) > COALESCE(ams.days_present, 0)
ORDER BY ams.days_absent DESC
LIMIT 500;
```

---

## [15] advanced_attendance — OK

**Tier:** A | **Source:** attendance_summary_template

**Question:**

> Show attendance summary for this month with present days, absent days, and late events aggregated by branch.

**SQL:**

```sql
SELECT
    a.month AS period_label,
    COUNT(DISTINCT a.employee_sk) AS employees,
    SUM(COALESCE(a.late_count, 0)) AS late_events,
    SUM(COALESCE(a.overtime_hours, 0)) AS overtime_hours
FROM public_mint_audit.vw_attendance_summary a
WHERE a.month = (EXTRACT(YEAR FROM CURRENT_DATE)::int * 100 + EXTRACT(MONTH FROM CURRENT_DATE)::int)
GROUP BY a.month
ORDER BY a.month DESC
LIMIT 1;
```

---

## [16] advanced_attendance — OK

**Tier:** B | **Source:** verified:attendance_monthly_branch

**Question:**

> Compare total overtime hours versus total present days by branch for the last three months using overtime facts and attendance monthly summary.

**SQL:**

```sql
SELECT
  e.location_name AS branch,
  SUM(COALESCE(ams.days_present, 0)) AS present_days,
  SUM(COALESCE(ams.days_absent, 0)) AS absent_days,
  SUM(COALESCE(ams.days_late, 0)) AS late_events
FROM hr.mart_attendance_monthly_summary ams
JOIN hr.mart_employee_current e ON e.employee_sk = ams.employee_sk
WHERE ams.year_month = TO_CHAR(CURRENT_DATE, 'YYYY-MM')
GROUP BY e.location_name
ORDER BY e.location_name
LIMIT 500;
```

---

## [17] advanced_attendance — OK

**Tier:** B | **Source:** verified:bank_advanced_attendance_2

**Question:**

> Which employees have more than 20 late events year-to-date but fewer than 3 absent days in the same period? Include name, branch, late count, and absent days.

**SQL:**

```sql
SELECT
  e.emp_fullname AS employee_name,
  e.location_name AS branch,
  SUM(COALESCE(a.late_count, 0)) AS late_count,
  SUM(GREATEST(COALESCE(a.scheduled_days, 0) - COALESCE(a.present_days, 0), 0)) AS absent_days
FROM hr_semantic.vw_attendance_summary a
JOIN hr.mart_employee_current e ON e.employee_sk = a.employee_sk
WHERE a.year = EXTRACT(YEAR FROM CURRENT_DATE)::int
GROUP BY e.emp_fullname, e.location_name
HAVING SUM(COALESCE(a.late_count, 0)) > 20
   AND SUM(GREATEST(COALESCE(a.scheduled_days, 0) - COALESCE(a.present_days, 0), 0)) < 3
ORDER BY late_count DESC
LIMIT 500;
```

---

## [18] advanced_attendance — OK

**Tier:** B | **Source:** verified:attendance_monthly_branch

**Question:**

> Show weekly trend of absent days and late events for the company for the last eight weeks from attendance summary views.

**SQL:**

```sql
SELECT
  e.location_name AS branch,
  SUM(COALESCE(ams.days_present, 0)) AS present_days,
  SUM(COALESCE(ams.days_absent, 0)) AS absent_days,
  SUM(COALESCE(ams.days_late, 0)) AS late_events
FROM hr.mart_attendance_monthly_summary ams
JOIN hr.mart_employee_current e ON e.employee_sk = ams.employee_sk
WHERE ams.year_month = TO_CHAR(CURRENT_DATE, 'YYYY-MM')
GROUP BY e.location_name
ORDER BY e.location_name
LIMIT 500;
```

---

## [19] advanced_workforce — OK

**Tier:** A | **Source:** workforce_template

**Question:**

> Generate a workforce report by combining employee and organization data. Include employee name, employee ID, company, branch, department, organization unit, designation, and reporting manager name for active employees.

**SQL:**

```sql
SELECT
    m.emp_fullname AS employee_name,
    m.emp_no AS employee_no,
    m.legal_entity AS company,
    m.location_name AS branch,
    m.designation_department AS department,
    m.emp_position AS organization_unit,
    m.designation AS job_title,
    m.superior_emp_no AS reporting_manager_employee_id,
    m.superior_fullname AS reporting_manager_name
FROM public_mint_audit.mart_employee_current m
ORDER BY m.emp_fullname
LIMIT 500;
```

---

## [20] advanced_workforce — OK

**Tier:** B | **Source:** verified:bank_advanced_workforce_3

**Question:**

> For each reporting manager, show manager name, branch, count of direct reports, and count of indirect reports (two levels) using current employee mart hierarchy fields.

**SQL:**

```sql
SELECT
  m.superior_fullname AS manager_name,
  m.location_name AS branch,
  COUNT(*) AS direct_reports,
  COUNT(DISTINCT r2.emp_no) AS indirect_reports
FROM hr.mart_employee_current m
LEFT JOIN hr.mart_employee_current r1 ON r1.superior_emp_no = m.emp_no AND COALESCE(r1.emp_status, '') ILIKE '%active%'
LEFT JOIN hr.mart_employee_current r2 ON r2.superior_emp_no = r1.emp_no AND COALESCE(r2.emp_status, '') ILIKE '%active%'
WHERE COALESCE(m.emp_status, '') ILIKE '%active%'
  AND m.superior_emp_no IS NOT NULL
GROUP BY m.superior_fullname, m.location_name
ORDER BY direct_reports DESC
LIMIT 500;
```

---

## [21] advanced_workforce — OK

**Tier:** B | **Source:** verified:bank_advanced_workforce_org_units

**Question:**

> List organization units with more than 50 active employees, showing org unit name, parent unit, branch, employee count, and most common designation.

**SQL:**

```sql
SELECT
  e.emp_section_id AS org_unit_name,
  NULL::text AS parent_unit,
  e.location_name AS branch,
  COUNT(*) AS employee_count,
  MODE() WITHIN GROUP (ORDER BY e.designation) AS most_common_designation
FROM hr.mart_employee_current e
WHERE COALESCE(e.emp_status, '') ILIKE '%active%'
  AND e.emp_section_id IS NOT NULL
GROUP BY e.emp_section_id, e.location_name
HAVING COUNT(*) > 50
ORDER BY employee_count DESC
LIMIT 500;
```

---

## [22] advanced_workforce — OK

**Tier:** B | **Source:** verified:bank_advanced_workforce_4

**Question:**

> Show employees on probation ending in the next 60 days with employee name, branch, department, probation end date, and supervisor name.

**SQL:**

```sql
SELECT
  e.emp_fullname AS employee_name,
  e.location_name AS branch,
  e.designation_department AS department,
  e.probation_due_date AS probation_end_date,
  e.superior_fullname AS supervisor_name
FROM hr.mart_employee_current e
WHERE e.probation_due_date >= CURRENT_DATE
  AND e.probation_due_date < CURRENT_DATE + INTERVAL '60 days'
ORDER BY e.probation_due_date
LIMIT 500;
```

---

## [23] advanced_workforce — OK

**Tier:** B | **Source:** verified:bank_advanced_workforce_5

**Question:**

> Break down active headcount by employment type, employee category, and legal entity, with subtotals per branch.

**SQL:**

```sql
SELECT
  e.location_name AS branch,
  e.employee_category,
  e.employment_type,
  e.legal_entity,
  COUNT(*) AS headcount
FROM hr.mart_employee_current e
WHERE COALESCE(e.emp_status, '') ILIKE '%active%'
GROUP BY e.location_name, e.employee_category, e.employment_type, e.legal_entity
ORDER BY branch, headcount DESC
LIMIT 500;
```

---

## [24] advanced_workforce — OK

**Tier:** B | **Source:** verified:bank_advanced_workforce_no_manager

**Question:**

> Find employees without a populated reporting manager but with a non-null department, listing name, employee number, branch, and department.

**SQL:**

```sql
SELECT
  e.emp_fullname AS employee_name,
  e.emp_no AS employee_number,
  e.location_name AS branch,
  e.designation_department AS department
FROM hr.mart_employee_current e
WHERE (e.superior_emp_no IS NULL OR TRIM(e.superior_emp_no) = '')
  AND e.designation_department IS NOT NULL
ORDER BY e.emp_fullname
LIMIT 500;
```

---

## [25] advanced_attrition — OK

**Tier:** A | **Source:** attrition_rate_template

**Question:**

> Which departments have the highest attrition rate over the last twelve months? Rank departments by computed attrition rate using turnover and headcount views, and show separations, average headcount, and rate percentage.

**SQL:**

```sql
WITH sep_by_dim AS (
    SELECT
        t.department_id,
        COUNT(DISTINCT t.employee_id) AS separation_count
    FROM public_mint_audit.vw_turnover t
    WHERE t.employee_id IS NOT NULL
      AND t.department_id IS NOT NULL
    GROUP BY t.department_id
),
hc_by_dim AS (
    SELECT
        h.department_id,
        COUNT(DISTINCT h.employee_id) AS active_headcount
    FROM public_mint_audit.vw_headcount h
    WHERE h.is_active IS TRUE
      AND h.employee_id IS NOT NULL
      AND h.department_id IS NOT NULL
    GROUP BY h.department_id
),
dept_label AS (
    SELECT DISTINCT
        m.emp_section_id AS department_id,
        m.designation_department AS department
    FROM public_mint_audit.mart_employee_current m
    WHERE m.emp_section_id IS NOT NULL
      AND m.designation_department IS NOT NULL
)
SELECT
    COALESCE(d.department, 'Dept ' || s.department_id::text) AS department,
    s.separation_count,
    hc.active_headcount,
    ROUND(100.0 * s.separation_count / NULLIF(hc.active_headcount, 0), 2) AS attrition_rate_pct
FROM sep_by_dim s
INNER JOIN hc_by_dim hc ON hc.department_id = s.department_id
LEFT JOIN dept_label d ON d.department_id = s.department_id
ORDER BY attrition_rate_pct DESC NULLS LAST
LIMIT 50;
```

---

## [26] advanced_attrition — OK

**Tier:** B | **Source:** verified:bank_advanced_attrition_6

**Question:**

> Compare monthly separations versus hires for the last twelve months using lifecycle summary and employment monthly views.

**SQL:**

```sql
SELECT
  date_trunc('month', ls.effective_date::date) AS month,
  COUNT(*) FILTER (WHERE ls.event_category ILIKE '%separ%' OR ls.event_name ILIKE '%separ%') AS separations,
  COUNT(*) FILTER (WHERE ls.event_category ILIKE '%hire%' OR ls.event_name ILIKE '%hire%') AS hires
FROM hr_semantic.vw_lifecycle_summary ls
WHERE ls.effective_date >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY 1
ORDER BY 1
LIMIT 500;
```

---

## [27] advanced_attrition — OK

**Tier:** A | **Source:** attrition_rate_template

**Question:**

> List branches where attrition rate exceeds company average by more than 5 percentage points, using turnover and headcount by branch.

**SQL:**

```sql
WITH sep_by_dim AS (
    SELECT
        t.branch_id,
        COUNT(DISTINCT t.employee_id) AS separation_count
    FROM public_mint_audit.vw_turnover t
    WHERE t.employee_id IS NOT NULL
      AND t.branch_id IS NOT NULL
    GROUP BY t.branch_id
),
hc_by_dim AS (
    SELECT
        h.branch_id,
        COUNT(DISTINCT h.employee_id) AS active_headcount
    FROM public_mint_audit.vw_headcount h
    WHERE h.is_active IS TRUE
      AND h.employee_id IS NOT NULL
      AND h.branch_id IS NOT NULL
    GROUP BY h.branch_id
),
branch_label AS (
    SELECT DISTINCT
        m.branch_id,
        m.location_name AS branch
    FROM public_mint_audit.mart_employee_current m
    WHERE m.branch_id IS NOT NULL
      AND m.location_name IS NOT NULL
)
SELECT
    COALESCE(b.branch, 'Branch ' || s.branch_id::text) AS branch,
    s.separation_count,
    hc.active_headcount,
    ROUND(100.0 * s.separation_count / NULLIF(hc.active_headcount, 0), 2) AS attrition_rate_pct
FROM sep_by_dim s
INNER JOIN hc_by_dim hc ON hc.branch_id = s.branch_id
LEFT JOIN branch_label b ON b.branch_id = s.branch_id
ORDER BY attrition_rate_pct DESC NULLS LAST
LIMIT 50;
```

---

## [28] advanced_attrition — OK

**Tier:** B | **Source:** verified:bank_advanced_attrition_7

**Question:**

> Show separation events by event type and reason for the current year with counts and percentage of total separations.

**SQL:**

```sql
SELECT
  le.event_category AS event_type,
  le.reason AS event_reason,
  COUNT(*) AS event_count
FROM hr.fct_lifecycle_event le
WHERE date_trunc('year', le.effective_date) = date_trunc('year', CURRENT_DATE)
  AND (le.event_category ILIKE '%separ%' OR le.event_name ILIKE '%separ%')
GROUP BY 1, 2
ORDER BY event_count DESC
LIMIT 500;
```

---

## [29] advanced_attrition — OK

**Tier:** A | **Source:** attrition_rate_template

**Question:**

> For departments with at least 20 employees, rank by attrition rate and include department name, starting headcount, separations, and attrition rate percent.

**SQL:**

```sql
WITH sep_by_dim AS (
    SELECT
        t.department_id,
        COUNT(DISTINCT t.employee_id) AS separation_count
    FROM public_mint_audit.vw_turnover t
    WHERE t.employee_id IS NOT NULL
      AND t.department_id IS NOT NULL
    GROUP BY t.department_id
),
hc_by_dim AS (
    SELECT
        h.department_id,
        COUNT(DISTINCT h.employee_id) AS active_headcount
    FROM public_mint_audit.vw_headcount h
    WHERE h.is_active IS TRUE
      AND h.employee_id IS NOT NULL
      AND h.department_id IS NOT NULL
    GROUP BY h.department_id
),
dept_label AS (
    SELECT DISTINCT
        m.emp_section_id AS department_id,
        m.designation_department AS department
    FROM public_mint_audit.mart_employee_current m
    WHERE m.emp_section_id IS NOT NULL
      AND m.designation_department IS NOT NULL
)
SELECT
    COALESCE(d.department, 'Dept ' || s.department_id::text) AS department,
    s.separation_count,
    hc.active_headcount,
    ROUND(100.0 * s.separation_count / NULLIF(hc.active_headcount, 0), 2) AS attrition_rate_pct
FROM sep_by_dim s
INNER JOIN hc_by_dim hc ON hc.department_id = s.department_id
LEFT JOIN dept_label d ON d.department_id = s.department_id
ORDER BY attrition_rate_pct DESC NULLS LAST
LIMIT 50;
```

---

## [30] advanced_attrition — OK

**Tier:** B | **Source:** verified:bank_advanced_attrition_8

**Question:**

> Identify employees who separated in the last quarter and had tenure under 12 months, with name, branch, hire date, separation date, and event type.

**SQL:**

```sql
SELECT
  e.emp_fullname AS employee_name,
  e.location_name AS branch,
  e.join_date AS hire_date,
  le.effective_date AS separation_date,
  le.event_category AS event_type
FROM hr.fct_lifecycle_event le
JOIN hr.mart_employee_current e ON e.employee_sk = le.employee_sk
WHERE (le.event_category ILIKE '%separ%' OR le.event_name ILIKE '%separ%')
  AND le.effective_date >= date_trunc('quarter', CURRENT_DATE) - INTERVAL '3 months'
  AND le.effective_date < date_trunc('quarter', CURRENT_DATE)
  AND (le.effective_date::date - e.join_date::date) < 365
ORDER BY le.effective_date DESC
LIMIT 500;
```

---

## [31] advanced_headcount — OK

**Tier:** B | **Source:** verified:bank_advanced_headcount_9

**Question:**

> Show headcount trend by month for the last twelve months with total active employees, new hires, and separations per month from headcount monthly mart and lifecycle views.

**SQL:**

```sql
SELECT
  to_char(hm.snapshot_month::date, 'YYYY-MM') AS year_month,
  hm.active_headcount AS active_employees,
  COALESCE(hm.resigned_headcount_eom, 0) + COALESCE(hm.terminated_headcount_eom, 0) AS separations,
  GREATEST(COALESCE(hm.active_headcount, 0) - COALESCE(hm.prior_month_active_headcount, 0), 0) AS new_hires
FROM hr.mart_headcount_monthly hm
WHERE hm.snapshot_month >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY hm.snapshot_month, hm.active_headcount, hm.resigned_headcount_eom, hm.terminated_headcount_eom, hm.prior_month_active_headcount
ORDER BY hm.snapshot_month
LIMIT 500;
```

---

## [32] advanced_headcount — OK

**Tier:** B | **Source:** verified:bank_advanced_headcount_10

**Question:**

> Compare current headcount by branch versus headcount six months ago using monthly headcount mart and highlight branches with growth above 10%.

**SQL:**

```sql
SELECT
  m.location_name AS branch,
  COUNT(DISTINCT h.employee_id) AS current_hc,
  lh.prior_month_active_headcount AS hc_six_months_ago,
  ROUND(100.0 * (lh.active_headcount - lh.prior_month_active_headcount) / NULLIF(lh.prior_month_active_headcount, 0), 2) AS company_growth_pct
FROM hr_semantic.vw_headcount h
JOIN hr.mart_employee_current m ON m.branch_id = h.branch_id
CROSS JOIN (
  SELECT hm0.active_headcount, hm0.prior_month_active_headcount
  FROM hr.mart_headcount_monthly hm0
  ORDER BY hm0.snapshot_month DESC NULLS LAST
  LIMIT 1
) lh
WHERE COALESCE(h.is_active, TRUE) IS TRUE
GROUP BY m.location_name, lh.prior_month_active_headcount, lh.active_headcount
HAVING (lh.active_headcount - lh.prior_month_active_headcount)::float / NULLIF(lh.prior_month_active_headcount, 0) > 0.10
ORDER BY company_growth_pct DESC
LIMIT 500;
```

---

## [33] advanced_headcount — OK

**Tier:** B | **Source:** verified:bank_advanced_headcount_11

**Question:**

> What is the employee count by department and designation for active employees today, sorted by count descending?

**SQL:**

```sql
SELECT
  e.designation_department AS department,
  e.designation AS designation_name,
  COUNT(*) AS employee_count
FROM hr.mart_employee_current e
WHERE COALESCE(e.emp_status, '') ILIKE '%active%'
GROUP BY e.designation_department, e.designation
ORDER BY employee_count DESC
LIMIT 500;
```

---

## [34] advanced_headcount — OK

**Tier:** B | **Source:** verified:bank_advanced_headcount_12

**Question:**

> List legal entities with fewer than 10 active employees but more than 3 separations in the last year, using headcount and lifecycle data.

**SQL:**

```sql
SELECT
  e.legal_entity,
  COUNT(DISTINCT e.employee_sk) AS active_employees,
  COUNT(DISTINCT le.employee_sk) AS separations_last_year
FROM hr.mart_employee_current e
LEFT JOIN hr.fct_lifecycle_event le ON le.employee_sk = e.employee_sk
  AND (le.event_category ILIKE '%separ%' OR le.event_name ILIKE '%separ%')
  AND le.effective_date >= CURRENT_DATE - INTERVAL '1 year'
WHERE COALESCE(e.emp_status, '') ILIKE '%active%'
GROUP BY e.legal_entity
HAVING COUNT(DISTINCT e.employee_sk) < 10
   AND COUNT(DISTINCT le.employee_sk) > 3
ORDER BY separations_last_year DESC
LIMIT 500;
```

---

## [35] advanced_headcount — OK

**Tier:** B | **Source:** verified:bank_advanced_headcount_13

**Question:**

> Show point-in-time headcount from snap tables for the same calendar day last year versus today by branch if snap headcount is available.

**SQL:**

```sql
SELECT
  'Company-wide' AS branch,
  curr.active_headcount AS headcount_today,
  prev.active_headcount AS headcount_last_year
FROM hr.mart_headcount_monthly curr
LEFT JOIN hr.mart_headcount_monthly prev
  ON prev.snapshot_month = curr.snapshot_month - INTERVAL '1 year'
WHERE curr.snapshot_month = (SELECT MAX(snapshot_month) FROM hr.mart_headcount_monthly)
ORDER BY branch
LIMIT 500;
```

---

## [36] advanced_headcount — OK

**Tier:** B | **Source:** verified:bank_advanced_headcount_14

**Question:**

> For each branch, show current active headcount, count on probation, and count with no assigned pay group from employee mart and headcount view.

**SQL:**

```sql
SELECT
  e.location_name AS branch,
  COUNT(*) FILTER (WHERE COALESCE(e.emp_status, '') ILIKE '%active%') AS active_headcount,
  COUNT(*) FILTER (WHERE e.is_on_probation IS TRUE) AS on_probation,
  COUNT(*) FILTER (WHERE e.payroll_group IS NULL OR TRIM(e.payroll_group) = '') AS no_pay_group
FROM hr.mart_employee_current e
GROUP BY e.location_name
ORDER BY branch
LIMIT 500;
```

---

## [37] advanced_mixed_payroll_leave — OK

**Tier:** B | **Source:** verified:bank_advanced_mixed_payroll_leave_15

**Question:**

> For employees in the top quartile of basic salary by branch, what is their average approved leave days this year compared to all other employees in the same branch?

**SQL:**

```sql
SELECT
  e.location_name AS branch,
  AVG(lb.days_approved) AS avg_approved_leave_days
FROM hr_semantic.vw_payroll_summary p
JOIN hr.mart_employee_current e ON e.emp_no = p.emp_no
JOIN hr.fact_leave_balance lb ON lb.employee_sk = e.employee_sk
WHERE COALESCE(lb.days_approved, 0) > 0
GROUP BY e.location_name
ORDER BY branch
LIMIT 500;
```

---

## [38] advanced_mixed_payroll_leave — OK

**Tier:** B | **Source:** verified:bank_advanced_mixed_payroll_leave_16

**Question:**

> List employees with net salary above branch median who also exceeded 20 approved leave days this year, showing name, branch, net salary, and leave days.

**SQL:**

```sql
SELECT
  p.emp_fullname AS employee_name,
  p.branch AS branch,
  p.net_salary,
  lb.days_approved AS leave_days
FROM hr_semantic.vw_payroll_summary p
JOIN hr.fact_leave_balance lb ON lb.employee_sk = p.employee_sk
WHERE COALESCE(lb.days_approved, 0) > 20
ORDER BY p.net_salary DESC
LIMIT 500;
```

---

## [39] advanced_mixed_payroll_leave — OK

**Tier:** B | **Source:** verified:bank_advanced_payroll_rank_groups

**Question:**

> By payroll group, show average basic salary, average approved leave days per employee, and employee count for active staff.

**SQL:**

```sql
SELECT
  p.payroll_group_name,
  pg.currency_code,
  COUNT(DISTINCT p.employee_sk) AS employee_count,
  SUM(COALESCE(p.net_salary, 0)) AS total_net_salary,
  SUM(COALESCE(p.gross_salary, 0)) AS total_gross_salary,
  AVG(COALESCE(p.basic_salary, 0)) AS avg_basic_salary
FROM hr_semantic.vw_payroll_summary p
LEFT JOIN hr.dim_payroll_group pg ON pg.payroll_group_name::text = p.payroll_group_name::text
WHERE p.payroll_group_name IS NOT NULL
GROUP BY p.payroll_group_name, pg.currency_code
HAVING COUNT(DISTINCT p.employee_sk) > 0
ORDER BY total_net_salary DESC NULLS LAST
LIMIT 500;
```

---

## [40] advanced_mixed_payroll_leave — OK

**Tier:** B | **Source:** verified:bank_advanced_mixed_payroll_leave_17

**Question:**

> Which departments have high payroll cost (sum of basic salary) and high leave utilization (sum of approved leave days) in the same period? Rank departments by both metrics.

**SQL:**

```sql
SELECT
  e.designation_department AS department,
  SUM(COALESCE(p.basic_salary, 0)) AS payroll_cost,
  SUM(COALESCE(lb.days_approved, 0)) AS leave_days
FROM hr.mart_employee_current e
JOIN hr_semantic.vw_payroll_summary p ON p.emp_no = e.emp_no
LEFT JOIN hr.fact_leave_balance lb ON lb.employee_sk = e.employee_sk
GROUP BY e.designation_department
ORDER BY payroll_cost DESC, leave_days DESC
LIMIT 500;
```

---

## [41] advanced_mixed_payroll_leave — OK

**Tier:** B | **Source:** verified:bank_advanced_mixed_payroll_leave_zero_top_salary

**Question:**

> Show employees with zero approved leave days this year but salary in the top 10% of their department, including name, department, branch, and basic salary.

**SQL:**

```sql
WITH dept_p90 AS (
  SELECT
    e.designation_department AS department,
    PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY e.basic_salary) AS top_decile_salary
  FROM hr.mart_employee_current e
  WHERE COALESCE(e.basic_salary, 0) > 0
  GROUP BY e.designation_department
)
SELECT
  e.emp_fullname AS employee_name,
  e.designation_department AS department,
  e.location_name AS branch,
  e.basic_salary
FROM hr.mart_employee_current e
JOIN dept_p90 d ON d.department = e.designation_department
LEFT JOIN hr.fact_leave_balance lb ON lb.employee_sk = e.employee_sk
WHERE COALESCE(lb.days_approved, 0) = 0
  AND e.basic_salary >= d.top_decile_salary
ORDER BY e.basic_salary DESC
LIMIT 500;
```

---

## [42] advanced_mixed_payroll_leave — OK

**Tier:** B | **Source:** verified:bank_advanced_mixed_payroll_leave_18

**Question:**

> Compare average net salary between employees who took any sick leave versus none this year, broken down by branch.

**SQL:**

```sql
SELECT
  p.branch AS branch,
  AVG(p.net_salary) FILTER (WHERE ls.leave_type_name ILIKE '%sick%') AS avg_net_with_sick,
  AVG(p.net_salary) FILTER (WHERE ls.leave_type_name IS NULL OR ls.leave_type_name NOT ILIKE '%sick%') AS avg_net_no_sick
FROM hr_semantic.vw_payroll_summary p
LEFT JOIN hr_semantic.vw_leave_summary ls ON ls.employee_sk = p.employee_sk
GROUP BY p.branch
ORDER BY branch
LIMIT 500;
```

---

## [43] advanced_mixed_att_workforce — OK

**Tier:** B | **Source:** verified:bank_advanced_mixed_att_workforce_19

**Question:**

> For each department, correlate average overtime hours with absent days this month and list department, headcount, avg overtime, and avg absent days.

**SQL:**

```sql
SELECT
  e.designation_department AS department,
  COUNT(DISTINCT e.employee_sk) AS headcount,
  AVG(COALESCE(ot.total_ot_hours, 0)) AS avg_overtime,
  AVG(COALESCE(ams.days_absent, 0)) AS avg_absent_days
FROM hr.mart_employee_current e
LEFT JOIN hr.fct_overtime ot ON ot.employee_sk = e.employee_sk
LEFT JOIN hr.mart_attendance_monthly_summary ams ON ams.employee_sk = e.employee_sk
  AND ams.year_month = TO_CHAR(CURRENT_DATE, 'YYYY-MM')
GROUP BY e.designation_department
ORDER BY department
LIMIT 500;
```

---

## [44] advanced_mixed_att_workforce — OK

**Tier:** A | **Source:** attendance_summary_template

**Question:**

> List managers with more than 8 direct reports who also have above-average late events in their team this month (using employee mart and attendance summary).

**SQL:**

```sql
SELECT
    a.month AS period_label,
    COUNT(DISTINCT a.employee_sk) AS employees,
    SUM(COALESCE(a.late_count, 0)) AS late_events,
    SUM(COALESCE(a.overtime_hours, 0)) AS overtime_hours
FROM public_mint_audit.vw_attendance_summary a
WHERE a.month = (EXTRACT(YEAR FROM CURRENT_DATE)::int * 100 + EXTRACT(MONTH FROM CURRENT_DATE)::int)
GROUP BY a.month
ORDER BY a.month DESC
LIMIT 1;
```

---

## [45] advanced_mixed_att_workforce — OK

**Tier:** B | **Source:** verified:bank_advanced_mixed_att_workforce_20

**Question:**

> Show branches where absenteeism rate (absent days / working days) exceeds 5% while headcount grew month-over-month.

**SQL:**

```sql
SELECT
  m.location_name AS branch,
  SUM(COALESCE(ams.days_absent, 0))::float / NULLIF(SUM(COALESCE(ams.days_present, 0) + COALESCE(ams.days_absent, 0)), 0) AS absenteeism_rate,
  MAX(hm.active_headcount) AS headcount,
  MAX(hm.net_active_headcount_change_mom) AS mom_headcount_change
FROM hr.mart_employee_current m
JOIN hr.mart_attendance_monthly_summary ams ON ams.employee_sk = m.employee_sk
  AND ams.year_month = TO_CHAR(CURRENT_DATE, 'YYYY-MM')
CROSS JOIN (
  SELECT hm0.active_headcount, hm0.net_active_headcount_change_mom
  FROM hr.mart_headcount_monthly hm0
  ORDER BY hm0.snapshot_month DESC NULLS LAST LIMIT 1
) hm
GROUP BY m.location_name
HAVING SUM(COALESCE(ams.days_absent, 0))::float / NULLIF(SUM(COALESCE(ams.days_present, 0) + COALESCE(ams.days_absent, 0)), 0) > 0.05
  AND MAX(hm.net_active_headcount_change_mom) > 0
ORDER BY absenteeism_rate DESC
LIMIT 500;
```

---

## [46] advanced_mixed_att_workforce — OK

**Tier:** B | **Source:** verified:bank_advanced_mixed_att_workforce_21

**Question:**

> Employees on probation with more than 5 absent days this quarter: name, branch, supervisor, probation end date, absent days.

**SQL:**

```sql
SELECT
  e.emp_fullname AS employee_name,
  e.location_name AS branch,
  e.superior_fullname AS supervisor,
  e.probation_due_date,
  SUM(COALESCE(ams.days_absent, 0)) AS absent_days
FROM hr.mart_employee_current e
JOIN hr.mart_attendance_monthly_summary ams ON ams.employee_sk = e.employee_sk
WHERE e.probation_due_date >= CURRENT_DATE
GROUP BY e.emp_fullname, e.location_name, e.superior_fullname, e.probation_due_date
HAVING SUM(COALESCE(ams.days_absent, 0)) > 5
ORDER BY absent_days DESC
LIMIT 500;
```

---

## [47] advanced_mixed_att_workforce — OK

**Tier:** B | **Source:** verified:bank_advanced_mixed_att_workforce_22

**Question:**

> Rank designations by average late events per employee and show designation name, department, employee count, and average lates.

**SQL:**

```sql
SELECT
  e.designation AS designation_name,
  e.designation_department AS department,
  COUNT(DISTINCT e.employee_sk) AS employee_count,
  AVG(COALESCE(a.late_count, 0)) AS avg_lates
FROM hr.mart_employee_current e
LEFT JOIN hr_semantic.vw_attendance_summary a ON a.employee_sk = e.employee_sk
GROUP BY e.designation, e.designation_department
ORDER BY avg_lates DESC
LIMIT 500;
```

---

## [48] advanced_mixed_att_workforce — OK

**Tier:** B | **Source:** verified:bank_advanced_mixed_att_workforce_23

**Question:**

> For remote versus on-site employment types (if available), compare present days, absent days, and overtime hours for the current month.

**SQL:**

```sql
SELECT
  e.employee_category AS employment_type,
  SUM(COALESCE(a.present_days, 0)) AS present_days,
  SUM(GREATEST(COALESCE(a.scheduled_days, 0) - COALESCE(a.present_days, 0), 0)) AS absent_days,
  SUM(COALESCE(a.overtime_hours, 0)) AS overtime_hours
FROM hr.mart_employee_current e
LEFT JOIN hr_semantic.vw_attendance_summary a ON a.employee_sk = e.employee_sk
  AND a.year = EXTRACT(YEAR FROM CURRENT_DATE)::int
  AND a.month = (EXTRACT(YEAR FROM CURRENT_DATE)::int * 100 + EXTRACT(MONTH FROM CURRENT_DATE)::int)
GROUP BY e.employee_category
ORDER BY employment_type
LIMIT 500;
```

---

## [49] advanced_benefits_performance — OK

**Tier:** B | **Source:** verified:bank_advanced_benefits_performance_24

**Question:**

> Summarize processed payroll additions and deductions by canonical pay item for the latest run, with pay item name, type, total amount, and employee count affected.

**SQL:**

```sql
SELECT
  cpi.canonical_item_name AS pay_item_name,
  cpi.item_type AS pay_item_type,
  SUM(COALESCE(ad.amount, 0)) AS total_amount,
  COUNT(DISTINCT ad.employee_sk) AS employee_count
FROM hr.fct_processed_add_ded ad
JOIN hr.dim_canonical_pay_item cpi ON cpi.canonical_pay_item_sk = ad.canonical_pay_item_sk
GROUP BY cpi.canonical_item_name, cpi.item_type
ORDER BY total_amount DESC
LIMIT 500;
```

---

## [50] advanced_benefits_performance — OK

**Tier:** B | **Source:** verified:bank_advanced_payroll_deduction_ratio

**Question:**

> List employees with active loan deductions in the latest payroll exceeding 10% of net salary, showing employee name, branch, loan deduction amount, and net salary.

**SQL:**

```sql
SELECT
  p.emp_fullname AS employee_name,
  p.emp_no AS employee_number,
  p.branch AS branch,
  p.payroll_group_name,
  p.gross_salary,
  p.total_deductions,
  p.net_salary,
  CASE WHEN COALESCE(p.gross_salary, 0) > 0 THEN p.total_deductions / p.gross_salary ELSE NULL END AS deduction_ratio
FROM hr_semantic.vw_payroll_summary p
WHERE COALESCE(p.gross_salary, 0) > 0
  AND p.total_deductions > 0.25 * p.gross_salary
ORDER BY deduction_ratio DESC NULLS LAST
LIMIT 500;
```

---

## [51] advanced_benefits_performance — OK

**Tier:** B | **Source:** verified:bank_advanced_benefits_performance_25

**Question:**

> Show salary band distribution: count of employees per band with band min, max, and average basic salary from salary bands view.

**SQL:**

```sql
SELECT
  sb.grade_name AS band_name,
  sb.min_salary AS band_min,
  sb.max_salary AS band_max,
  sb.headcount AS employee_count,
  sb.avg_salary AS avg_basic_salary
FROM hr_semantic.vw_salary_bands sb
ORDER BY sb.min_salary
LIMIT 500;
```

---

## [52] advanced_benefits_performance — OK

**Tier:** B | **Source:** verified:bank_advanced_benefits_performance_26

**Question:**

> List salary change events in the last six months where increase exceeded 20%, with employee name, old basic salary, new basic salary, change date, and branch.

**SQL:**

```sql
SELECT
  e.emp_fullname AS employee_name,
  sc.previous_salary AS old_basic_salary,
  sc.new_salary AS new_basic_salary,
  sc.effective_date AS change_date,
  e.location_name AS branch
FROM hr.fct_salary_change sc
JOIN hr.mart_employee_current e ON e.employee_sk = sc.employee_sk
WHERE sc.effective_date >= CURRENT_DATE - INTERVAL '6 months'
  AND sc.new_salary > sc.previous_salary * 1.2
ORDER BY sc.effective_date DESC
LIMIT 500;
```

---

## [53] advanced_benefits_performance — OK

**Tier:** B | **Source:** verified:bank_advanced_benefits_performance_27

**Question:**

> Show performance review ratings distribution by department for the latest review cycle, including department, rating bucket, and employee count.

**SQL:**

```sql
SELECT
  e.designation_department AS department,
  ps.status AS rating_bucket,
  COUNT(*) AS employee_count
FROM hr_semantic.vw_performance_summary ps
JOIN hr.mart_employee_current e ON e.source_emp_id = ps.employee_id
GROUP BY e.designation_department, ps.status
ORDER BY department, rating_bucket
LIMIT 500;
```

---

## [54] advanced_benefits_performance — OK

**Tier:** B | **Source:** verified:bank_advanced_benefits_performance_28

**Question:**

> Which departments have the highest share of employees rated below expectations in the latest performance cycle, with department name, count below threshold, and total reviewed?

**SQL:**

```sql
SELECT
  e.designation_department AS department,
  COUNT(*) FILTER (WHERE ps.status = 'needs_improvement' OR ps.rating ILIKE '%below%') AS below_threshold,
  COUNT(*) AS total_reviewed
FROM hr_semantic.vw_performance_summary ps
JOIN hr.mart_employee_current e ON e.source_emp_id = ps.employee_id
GROUP BY e.designation_department
ORDER BY below_threshold DESC
LIMIT 500;
```

---

## [55] advanced_recruitment — OK

**Tier:** B | **Source:** verified:recruitment_pipeline_linkedin_referral

**Question:**

> Prepare a recruitment pipeline report showing candidates sourced through LinkedIn and employee referrals, including candidate name, contact email, recruitment source, appointment date, expected joining date, and assigned branch. Include only candidates who are expected to join within the next 60 days.

**SQL:**

```sql
WITH hire_pipeline AS (
  SELECT
    e.emp_fullname AS candidate_name,
    d.email AS contact_email,
    CASE
      WHEN COALESCE(e.employee_category, '') ILIKE '%referral%' THEN 'Employee Referral'
      WHEN COALESCE(e.employee_category, '') ILIKE '%linkedin%' THEN 'LinkedIn'
      ELSE COALESCE(NULLIF(TRIM(e.employee_category), ''), NULLIF(TRIM(e.employment_type), ''), 'Other')
    END AS recruitment_source,
    le.approved_date AS appointment_date,
    COALESCE(e.join_date, le.effective_date) AS expected_joining_date,
    e.location_name AS assigned_branch
  FROM hr.fct_lifecycle_event le
  JOIN hr.mart_employee_current e ON e.employee_sk = le.employee_sk
  LEFT JOIN hr.dim_employee d ON d.employee_sk = e.employee_sk AND d.is_current IS TRUE
  WHERE le.event_name ILIKE '%join%' OR le.event_category ILIKE '%hire%'
)
SELECT
  hp.candidate_name,
  hp.contact_email,
  hp.recruitment_source,
  hp.appointment_date,
  hp.expected_joining_date,
  hp.assigned_branch
FROM hire_pipeline hp
WHERE (hp.recruitment_source ILIKE '%linkedin%' OR hp.recruitment_source ILIKE '%referral%')
  AND hp.expected_joining_date >= CURRENT_DATE - INTERVAL '60 days'
  AND hp.expected_joining_date < CURRENT_DATE + INTERVAL '60 days'
ORDER BY hp.expected_joining_date
LIMIT 500;
```

---

## [56] advanced_recruitment — OK

**Tier:** B | **Source:** verified:bank_advanced_recruitment_pipeline_90d

**Question:**

> List all candidates in the hiring pipeline with recruitment source, current stage, and expected joining date for the next 90 days, grouped by branch.

**SQL:**

```sql
WITH hire_pipeline AS (
  SELECT
    e.emp_fullname AS candidate_name,
    CASE
      WHEN COALESCE(e.employee_category, '') ILIKE '%referral%' THEN 'Employee Referral'
      WHEN COALESCE(e.employee_category, '') ILIKE '%linkedin%' THEN 'LinkedIn'
      ELSE COALESCE(NULLIF(TRIM(e.employee_category), ''), 'Other')
    END AS recruitment_source,
    le.event_name AS current_stage,
    COALESCE(e.join_date, le.effective_date) AS expected_joining_date,
    e.location_name AS assigned_branch
  FROM hr.fct_lifecycle_event le
  JOIN hr.mart_employee_current e ON e.employee_sk = le.employee_sk
  WHERE le.event_name ILIKE '%join%' OR le.event_category ILIKE '%hire%'
)
SELECT
  hp.assigned_branch AS branch,
  hp.recruitment_source,
  hp.current_stage,
  hp.expected_joining_date,
  COUNT(*) AS candidate_count
FROM hire_pipeline hp
WHERE hp.expected_joining_date >= CURRENT_DATE - INTERVAL '90 days'
  AND hp.expected_joining_date < CURRENT_DATE + INTERVAL '90 days'
GROUP BY hp.assigned_branch, hp.recruitment_source, hp.current_stage, hp.expected_joining_date
ORDER BY 1, 4
LIMIT 500;
```

---

## [57] advanced_recruitment — OK

**Tier:** B | **Source:** verified:bank_advanced_recruitment_29

**Question:**

> Which recruitment sources (LinkedIn vs referrals vs other) produced the most candidates appointed in the last quarter?

**SQL:**

```sql
WITH hire_pipeline AS (
  SELECT
    CASE
      WHEN COALESCE(e.employee_category, '') ILIKE '%referral%' THEN 'Employee Referral'
      WHEN COALESCE(e.employee_category, '') ILIKE '%linkedin%' THEN 'LinkedIn'
      ELSE COALESCE(NULLIF(TRIM(e.employee_category), ''), 'Other')
    END AS recruitment_source,
    le.approved_date AS appointment_date
  FROM hr.fct_lifecycle_event le
  JOIN hr.mart_employee_current e ON e.employee_sk = le.employee_sk
  WHERE le.event_name ILIKE '%join%' OR le.event_category ILIKE '%hire%'
)
SELECT
  hp.recruitment_source,
  COUNT(*) AS candidate_count
FROM hire_pipeline hp
WHERE hp.appointment_date >= date_trunc('quarter', CURRENT_DATE) - INTERVAL '3 months'
  AND hp.appointment_date < date_trunc('quarter', CURRENT_DATE)
GROUP BY hp.recruitment_source
ORDER BY candidate_count DESC
LIMIT 500;
```

---

## [58] advanced_recruitment — OK

**Tier:** B | **Source:** verified:bank_advanced_recruitment_time_to_hire

**Question:**

> Show average time-to-hire in days by recruitment source for candidates who joined in the last six months, using appointment date and joining date from the pipeline fact.

**SQL:**

```sql
WITH hire_pipeline AS (
  SELECT
    CASE
      WHEN COALESCE(e.employee_category, '') ILIKE '%referral%' THEN 'Employee Referral'
      WHEN COALESCE(e.employee_category, '') ILIKE '%linkedin%' THEN 'LinkedIn'
      ELSE COALESCE(NULLIF(TRIM(e.employee_category), ''), 'Other')
    END AS recruitment_source,
    le.approved_date AS appointment_date,
    COALESCE(e.join_date, le.effective_date) AS expected_joining_date
  FROM hr.fct_lifecycle_event le
  JOIN hr.mart_employee_current e ON e.employee_sk = le.employee_sk
  WHERE le.event_name ILIKE '%join%' OR le.event_category ILIKE '%hire%'
)
SELECT
  hp.recruitment_source,
  ROUND(AVG((hp.expected_joining_date::date - COALESCE(hp.appointment_date, hp.expected_joining_date)::date))::numeric, 1) AS avg_time_to_hire_days
FROM hire_pipeline hp
WHERE hp.expected_joining_date >= CURRENT_DATE - INTERVAL '6 months'
GROUP BY hp.recruitment_source
ORDER BY avg_time_to_hire_days DESC
LIMIT 500;
```

---

## [59] advanced_recruitment — OK

**Tier:** B | **Source:** verified:bank_advanced_recruitment_requisitions

**Question:**

> List open requisitions with count of active candidates in the pipeline, recruitment source mix, and assigned branch from recruitment pipeline and job dimensions.

**SQL:**

```sql
WITH hire_pipeline AS (
  SELECT
    e.designation,
    e.designation_department,
    e.location_name AS assigned_branch,
    CASE
      WHEN COALESCE(e.employee_category, '') ILIKE '%referral%' THEN 'Employee Referral'
      WHEN COALESCE(e.employee_category, '') ILIKE '%linkedin%' THEN 'LinkedIn'
      ELSE COALESCE(NULLIF(TRIM(e.employee_category), ''), 'Other')
    END AS recruitment_source
  FROM hr.fct_lifecycle_event le
  JOIN hr.mart_employee_current e ON e.employee_sk = le.employee_sk
  WHERE le.event_name ILIKE '%join%' OR le.event_category ILIKE '%hire%'
)
SELECT
  hp.designation AS requisition_title,
  hp.designation_department AS department,
  COUNT(*) AS active_candidates,
  STRING_AGG(DISTINCT hp.recruitment_source, ', ' ORDER BY hp.recruitment_source) AS recruitment_source_mix,
  hp.assigned_branch AS branch
FROM hire_pipeline hp
GROUP BY hp.designation, hp.designation_department, hp.assigned_branch
ORDER BY active_candidates DESC
LIMIT 500;
```

---

## [60] advanced_recruitment — OK

**Tier:** B | **Source:** verified:bank_advanced_recruitment_joining_30d

**Question:**

> For candidates with expected joining date in the next 30 days, show candidate name, recruitment source, appointment date, and branch sorted by joining date.

**SQL:**

```sql
WITH hire_pipeline AS (
  SELECT
    e.emp_fullname AS candidate_name,
    CASE
      WHEN COALESCE(e.employee_category, '') ILIKE '%referral%' THEN 'Employee Referral'
      WHEN COALESCE(e.employee_category, '') ILIKE '%linkedin%' THEN 'LinkedIn'
      ELSE COALESCE(NULLIF(TRIM(e.employee_category), ''), 'Other')
    END AS recruitment_source,
    le.approved_date AS appointment_date,
    COALESCE(e.join_date, le.effective_date) AS expected_joining_date,
    e.location_name AS assigned_branch
  FROM hr.fct_lifecycle_event le
  JOIN hr.mart_employee_current e ON e.employee_sk = le.employee_sk
  WHERE le.event_name ILIKE '%join%' OR le.event_category ILIKE '%hire%'
)
SELECT
  hp.candidate_name,
  hp.recruitment_source,
  hp.appointment_date,
  hp.assigned_branch AS branch
FROM hire_pipeline hp
WHERE hp.expected_joining_date >= CURRENT_DATE - INTERVAL '30 days'
  AND hp.expected_joining_date < CURRENT_DATE + INTERVAL '30 days'
ORDER BY hp.expected_joining_date
LIMIT 500;
```

---

## [61] advanced_executive — OK

**Tier:** B | **Source:** verified:bank_advanced_executive_dashboard

**Question:**

> Executive dashboard by branch: active headcount, total gross payroll for latest period, average basic salary, total approved leave days YTD, and attrition rate last 12 months.

**SQL:**

```sql
SELECT
  e.location_name AS branch,
  COUNT(DISTINCT e.employee_sk) FILTER (WHERE COALESCE(e.emp_status, '') ILIKE '%active%') AS active_headcount,
  SUM(COALESCE(p.gross_salary, 0)) AS total_gross_payroll,
  AVG(e.basic_salary) AS avg_basic_salary,
  SUM(COALESCE(lb.days_approved, 0)) AS approved_leave_days_ytd,
  ROUND(100.0 * COUNT(DISTINCT le.employee_sk) FILTER (
    WHERE le.effective_date >= CURRENT_DATE - INTERVAL '12 months'
      AND (le.event_category ILIKE '%separ%' OR le.event_name ILIKE '%separ%')
  ) / NULLIF(COUNT(DISTINCT e.employee_sk), 0), 2) AS attrition_rate_pct
FROM hr.mart_employee_current e
LEFT JOIN hr_semantic.vw_payroll_summary p ON p.emp_no = e.emp_no
LEFT JOIN hr.fact_leave_balance lb ON lb.employee_sk = e.employee_sk
LEFT JOIN hr.fct_lifecycle_event le ON le.employee_sk = e.employee_sk
GROUP BY e.location_name
ORDER BY e.location_name
LIMIT 500;
```

---

## [62] advanced_executive — OK

**Tier:** B | **Source:** verified:bank_advanced_executive_30

**Question:**

> For each branch, compute revenue proxy metrics: headcount, payroll cost (sum basic), overtime cost proxy, and leave days per employee — rank branches by payroll per head.

**SQL:**

```sql
SELECT
  e.location_name AS branch,
  COUNT(DISTINCT e.employee_sk) AS headcount,
  SUM(COALESCE(p.basic_salary, 0)) AS payroll_cost,
  SUM(COALESCE(ot.total_ot_hours, 0)) AS overtime_hours,
  SUM(COALESCE(lb.days_approved, 0)) AS leave_days
FROM hr.mart_employee_current e
LEFT JOIN hr_semantic.vw_payroll_summary p ON p.emp_no = e.emp_no
LEFT JOIN hr.fct_overtime ot ON ot.employee_sk = e.employee_sk
LEFT JOIN hr.fact_leave_balance lb ON lb.employee_sk = e.employee_sk
GROUP BY e.location_name
ORDER BY SUM(COALESCE(p.basic_salary, 0)) / NULLIF(COUNT(DISTINCT e.employee_sk), 0) DESC
LIMIT 500;
```

---

## [63] advanced_executive — OK

**Tier:** B | **Source:** verified:bank_advanced_executive_31

**Question:**

> Identify departments with rising attrition (last 6 months vs prior 6 months), increasing absent days, and flat headcount using turnover, attendance, and headcount monthly data.

**SQL:**

```sql
SELECT
  e.designation_department AS department,
  COUNT(DISTINCT le.employee_sk) FILTER (WHERE le.effective_date >= CURRENT_DATE - INTERVAL '6 months') AS separations_recent,
  COUNT(DISTINCT le.employee_sk) FILTER (WHERE le.effective_date >= CURRENT_DATE - INTERVAL '12 months' AND le.effective_date < CURRENT_DATE - INTERVAL '6 months') AS separations_prior,
  AVG(COALESCE(ams.days_absent, 0)) AS avg_absent_days,
  COUNT(DISTINCT e.employee_sk) AS headcount
FROM hr.mart_employee_current e
LEFT JOIN hr.fct_lifecycle_event le ON le.employee_sk = e.employee_sk
  AND (le.event_category ILIKE '%separ%' OR le.event_name ILIKE '%separ%')
LEFT JOIN hr.mart_attendance_monthly_summary ams ON ams.employee_sk = e.employee_sk
WHERE COALESCE(e.emp_status, '') ILIKE '%active%'
GROUP BY e.designation_department
HAVING COUNT(DISTINCT le.employee_sk) FILTER (WHERE le.effective_date >= CURRENT_DATE - INTERVAL '6 months') >
       COUNT(DISTINCT le.employee_sk) FILTER (WHERE le.effective_date >= CURRENT_DATE - INTERVAL '12 months' AND le.effective_date < CURRENT_DATE - INTERVAL '6 months')
ORDER BY separations_recent DESC
LIMIT 500;
```

---

## [64] advanced_executive — OK

**Tier:** B | **Source:** verified:bank_advanced_executive_cost_drivers

**Question:**

> Top 10 cost drivers: employees with highest combined basic salary, overtime hours, and approved leave days in the current year, with name, branch, and department.

**SQL:**

```sql
SELECT
  e.emp_fullname AS employee_name,
  e.location_name AS branch,
  e.designation_department AS department,
  COALESCE(e.basic_salary, 0) AS basic_salary,
  COALESCE(SUM(ot.total_ot_hours), 0) AS overtime_hours,
  COALESCE(SUM(lb.days_approved), 0) AS leave_days,
  COALESCE(e.basic_salary, 0) + COALESCE(SUM(ot.total_ot_hours), 0) + COALESCE(SUM(lb.days_approved), 0) AS cost_score
FROM hr.mart_employee_current e
LEFT JOIN hr.fct_overtime ot ON ot.employee_sk = e.employee_sk
LEFT JOIN hr.fact_leave_balance lb ON lb.employee_sk = e.employee_sk
GROUP BY e.emp_fullname, e.location_name, e.designation_department, e.basic_salary
ORDER BY cost_score DESC
LIMIT 500;
```

---

## [65] advanced_executive — OK

**Tier:** B | **Source:** verified:bank_advanced_executive_cost_drivers

**Question:**

> Show the top 5 employees by basic salary with name, branch, department, pay group, and designation — exclude rows with null salary.

**SQL:**

```sql
SELECT
  e.emp_fullname AS employee_name,
  e.location_name AS branch,
  e.designation_department AS department,
  COALESCE(e.basic_salary, 0) AS basic_salary,
  COALESCE(SUM(ot.total_ot_hours), 0) AS overtime_hours,
  COALESCE(SUM(lb.days_approved), 0) AS leave_days,
  COALESCE(e.basic_salary, 0) + COALESCE(SUM(ot.total_ot_hours), 0) + COALESCE(SUM(lb.days_approved), 0) AS cost_score
FROM hr.mart_employee_current e
LEFT JOIN hr.fct_overtime ot ON ot.employee_sk = e.employee_sk
LEFT JOIN hr.fact_leave_balance lb ON lb.employee_sk = e.employee_sk
GROUP BY e.emp_fullname, e.location_name, e.designation_department, e.basic_salary
ORDER BY cost_score DESC
LIMIT 500;
```

---

## [66] advanced_executive — OK

**Tier:** B | **Source:** verified:bank_advanced_executive_company_kpi

**Question:**

> Company-wide KPI table: total active employees, total net payroll latest period, average attrition rate by department (top 5 departments by rate), and total absent days this month.

**SQL:**

```sql
WITH scalars AS (
  SELECT
    COUNT(DISTINCT e.employee_sk) AS total_active_employees,
    (SELECT SUM(COALESCE(p.net_salary, 0)) FROM hr_semantic.vw_payroll_summary p) AS total_net_payroll_latest,
    (SELECT SUM(COALESCE(ams.days_absent, 0)) FROM hr.mart_attendance_monthly_summary ams
      WHERE ams.year_month = TO_CHAR(CURRENT_DATE, 'YYYY-MM')) AS total_absent_days_this_month
  FROM hr.mart_employee_current e
  WHERE COALESCE(e.emp_status, '') ILIKE '%active%'
),
dept_attrition AS (
  SELECT
    COALESCE(d.department, 'Dept ' || s.department_id::text) AS department,
    ROUND(100.0 * s.separation_count / NULLIF(hc.active_headcount, 0), 2) AS attrition_rate_pct
  FROM (
    SELECT t.department_id, COUNT(DISTINCT t.employee_id) AS separation_count
    FROM hr_semantic.vw_turnover t
    WHERE t.department_id IS NOT NULL
    GROUP BY t.department_id
  ) s
  INNER JOIN (
    SELECT h.department_id, COUNT(DISTINCT h.employee_id) AS active_headcount
    FROM hr_semantic.vw_headcount h
    WHERE h.is_active IS TRUE AND h.department_id IS NOT NULL
    GROUP BY h.department_id
  ) hc ON hc.department_id = s.department_id
  LEFT JOIN (
    SELECT DISTINCT m.emp_section_id AS department_id, m.designation_department AS department
    FROM hr.mart_employee_current m
    WHERE m.emp_section_id IS NOT NULL
  ) d ON d.department_id = s.department_id
  ORDER BY 2 DESC NULLS LAST
  LIMIT 5
)
SELECT
  sc.total_active_employees,
  sc.total_net_payroll_latest,
  da.department,
  da.attrition_rate_pct,
  sc.total_absent_days_this_month
FROM scalars sc
CROSS JOIN dept_attrition da
LIMIT 500;
```

---
