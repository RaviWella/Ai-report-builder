# Business Glossary

Independent business terms for MintHRM analytics.

## Employee

**Definition:** A person employed by the organization with a unique employee number (emp_no) in MintHRM.  
**Formula:** TBD  
**Owner:** HR Analytics  

## Headcount

**Definition:** Count of employees in active employment status at a point in time or month-end.  
**Formula:** COUNT(employee_sk) WHERE emp_status = 'active' AND is_current = true  
**Owner:** HR Analytics  

## Active Employee

**Definition:** Employee whose current employment status is active in dim_employee.  
**Formula:** emp_status = 'active' AND is_current = true  
**Owner:** HR Analytics  

## Termination

**Definition:** End of employment due to resignation, termination, or retirement recorded in lifecycle events.  
**Formula:** TBD — see fct_lifecycle_event  
**Owner:** HR Analytics  

## Leave Balance

**Definition:** Remaining entitled leave days for an employee and leave type at a snapshot date.  
**Formula:** remaining_days from fct_leave_balance_snapshot / vw_current_leave_balance  
**Owner:** HR Operations  

## Leave Entitlement

**Definition:** Total leave days granted to an employee for a leave type and entitlement period.  
**Formula:** entitled_days from fct_leave_balance_snapshot  
**Owner:** HR Operations  

## Attendance

**Definition:** Daily record of employee presence, absence, lateness, and worked hours.  
**Formula:** TBD — fct_daily_attendance grain  
**Owner:** Workforce Analytics  

## Overtime

**Definition:** Hours worked beyond scheduled shift, captured in attendance or payroll attendance lines.  
**Formula:** SUM(total_ot_hours) or SUM(overtime_pay)  
**Owner:** Workforce Analytics  

## Payroll

**Definition:** Processed salary outputs from the MintHRM payroll engine (not recalculated in the warehouse).  
**Formula:** TBD  
**Owner:** Payroll  

## Gross Salary

**Definition:** Total earnings before deductions for a pay period.  
**Formula:** SUM(gross_salary) from fct_processed_salary  
**Owner:** Payroll  

## Net Salary

**Definition:** Take-home pay after tax and other deductions for a pay period.  
**Formula:** SUM(net_salary) from fct_processed_salary  
**Owner:** Payroll  

## Department

**Definition:** Organizational unit assigned to an employee, derived from org hierarchy or designation.  
**Formula:** TBD — department_name on dim_employee  
**Owner:** HR Analytics  

## Designation

**Definition:** Job title or role assigned to an employee.  
**Formula:** TBD — designation_name on dim_employee  
**Owner:** HR Analytics  

## Cost Center

**Definition:** Financial attribution unit for employee cost; sourced from employment attributes when available.  
**Formula:** TBD  
**Owner:** Finance  

## Turnover Rate

**Definition:** Rate at which employees leave the organization over a period.  
**Formula:** TBD — vw_turnover / lifecycle facts  
**Owner:** HR Analytics  

## Absenteeism

**Definition:** Rate or count of unplanned absence days relative to scheduled work days.  
**Formula:** days_absent / (days_present + days_absent) from mart_attendance_monthly_summary  
**Owner:** Workforce Analytics  

## FTE

**Definition:** Full-time equivalent headcount; not explicitly modeled — TBD if fractional FTE is required.  
**Formula:** TBD  
**Owner:** HR Analytics  
