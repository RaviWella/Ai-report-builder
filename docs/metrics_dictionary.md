# Metrics Dictionary

Standard HR analytics metrics.

## Headcount

**Description:** Current active workforce at month-end.  
**Formula:** SUM(active_headcount)  
**Filters:** snapshot_month = reporting month  
**Source:** `vw_headcount / mart_headcount_monthly`  
**Aggregation:** SUM  
**Business Owner:** HR  

## Joiners

**Description:** Employees who joined in the reporting period.  
**Formula:** COUNT lifecycle join events  
**Filters:** event_category = join; effective_date in period  
**Source:** `fct_lifecycle_event / vw_lifecycle_summary`  
**Aggregation:** COUNT  
**Business Owner:** HR  

## Leavers

**Description:** Employees who left in the reporting period.  
**Formula:** COUNT lifecycle exit events  
**Filters:** resignation/termination events in period  
**Source:** `fct_lifecycle_event / vw_turnover`  
**Aggregation:** COUNT  
**Business Owner:** HR  

## Turnover Rate

**Description:** Leavers relative to average headcount in period.  
**Formula:** TBD  
**Filters:** TBD  
**Source:** `vw_turnover`  
**Aggregation:** TBD  
**Business Owner:** HR  

## Absenteeism Rate

**Description:** Share of scheduled days marked absent.  
**Formula:** SUM(days_absent) / NULLIF(SUM(days_present + days_absent), 0)  
**Filters:** mart_attendance_monthly_summary  
**Source:** `vw_attendance_summary`  
**Aggregation:** Ratio  
**Business Owner:** Workforce  

## Leave Utilization

**Description:** Approved leave days used relative to entitlement.  
**Formula:** approved_leave_days / total_entitled_days  
**Filters:** vw_leave_utilization when available  
**Source:** `vw_leave_utilization / mart_leave_monthly_summary`  
**Aggregation:** Ratio  
**Business Owner:** HR  

## Overtime Hours

**Description:** Total overtime hours in period.  
**Formula:** SUM(total_overtime_hours)  
**Filters:** year_month in period  
**Source:** `mart_attendance_monthly_summary / vw_attendance_summary`  
**Aggregation:** SUM  
**Business Owner:** Workforce  

## Gross Payroll

**Description:** Total gross pay for processed payroll runs.  
**Formula:** SUM(gross_salary)  
**Filters:** process_status = processed  
**Source:** `fct_processed_salary / vw_payroll_summary`  
**Aggregation:** SUM  
**Business Owner:** Payroll  

## Net Payroll

**Description:** Total net pay for processed payroll runs.  
**Formula:** SUM(net_salary)  
**Filters:** process_status = processed  
**Source:** `fct_processed_salary / vw_payroll_summary`  
**Aggregation:** SUM  
**Business Owner:** Payroll  

## Department Headcount

**Description:** Active employees grouped by department.  
**Formula:** COUNT(employee_sk) GROUP BY department_name  
**Filters:** is_current = true AND emp_status = 'active'  
**Source:** `dim_employee / mart_employee_current`  
**Aggregation:** COUNT  
**Business Owner:** HR  

## Gender Ratio

**Description:** Distribution of employees by gender.  
**Formula:** COUNT by gender / total COUNT  
**Filters:** active employees  
**Source:** `mart_employee_current`  
**Aggregation:** Ratio  
**Business Owner:** HR  

## Average Tenure

**Description:** Mean years of service for active employees.  
**Formula:** AVG(tenure_years)  
**Filters:** mart_employee_current  
**Source:** `mart_employee_current`  
**Aggregation:** AVG  
**Business Owner:** HR  
