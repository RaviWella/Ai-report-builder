WITH emp_je AS (
    SELECT
        e.tenant_id,
        e.employee_sk,
        e.emp_no,
        COALESCE(NULLIF(TRIM(e.employee_category), ''), 'Unassigned')::varchar(128) AS je
    FROM {mart_schema}.dim_employee e
    WHERE e.tenant_id = '{tenant_id}'
      AND e.is_current = true
),

payroll_core AS (
    SELECT
        p.payroll_year                                          AS proc_year,
        p.payroll_month                                         AS proc_month,
        p.payroll_half                                          AS proc_half,
        ej.je,
        m.employee_sk,
        ej.emp_no,
        COALESCE(m.basic_salary, 0)                             AS basic_salary,
        COALESCE(m.ot_amount, 0)                                AS over_time,
        COALESCE(m.gross_salary, 0)                             AS gross_salary,
        COALESCE(m.net_salary, 0)                               AS net_salary,
        COALESCE(m.tax_amount, 0)                               AS apit,
        COALESCE(m.epf_employee_amount, 0)                      AS epf_8,
        COALESCE(m.epf_employer_amount, 0)                      AS epf_12,
        COALESCE(m.etf_amount, 0)                               AS etf_3,
        COALESCE(m.nopay_deduction, 0)                          AS no_pay_mart
    FROM {mart_schema}.mart_processed_payroll_summary m
    INNER JOIN {mart_schema}.dim_payroll_period p
        ON  p.payroll_period_sk = m.payroll_period_sk
       AND p.tenant_id = m.tenant_id
    INNER JOIN emp_je ej
        ON  ej.employee_sk = m.employee_sk
       AND ej.tenant_id = m.tenant_id
    WHERE m.tenant_id = '{tenant_id}'
      AND COALESCE(m.process_status, 'processed') = 'processed'
),

add_emp AS (
    SELECT
        p.payroll_year                                          AS proc_year,
        p.payroll_month                                         AS proc_month,
        p.payroll_half                                          AS proc_half,
        a.employee_sk,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%fuel%'
              OR lower(a.payroll_item_name) LIKE '%transport%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS fuel_transport_allowance,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%inflation%'
             AND lower(a.payroll_item_name) NOT LIKE '%arrear%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS inflation_allowance,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%dollar%'
              OR lower(a.payroll_item_name) LIKE '%pegged%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS dollar_pegged,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%car%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS car_allowance,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%blend%'
             AND lower(a.payroll_item_name) NOT LIKE '%recovery%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS blend_allowance,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%cricket%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS cricket_allowance,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%parent%'
              OR lower(a.payroll_item_name) LIKE '%child%benefit%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS parent_child_benefit,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%annual%leave%encash%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS annual_leave_encashment,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%earn%leave%encash%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS earn_leave_encashment,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%inflation%'
             AND lower(a.payroll_item_name) LIKE '%arrear%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS inflation_allowance_arrears,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%night%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS night_allowance,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%ot%arrear%'
              OR lower(a.payroll_item_name) LIKE '%over time%arrear%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS ot_arrears,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%salary%arrear%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS salary_arrears,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%sales%'
              OR lower(a.payroll_item_name) LIKE '%incentive%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS sales_incentive
    FROM {mart_schema}.fct_processed_add_ded a
    INNER JOIN {mart_schema}.dim_payroll_period p
        ON  p.payroll_period_sk = a.payroll_period_sk
       AND p.tenant_id = a.tenant_id
    WHERE a.tenant_id = '{tenant_id}'
      AND a.payroll_item_code IN ('1', '3')
      AND COALESCE(a.amount, 0) <> 0
      AND lower(COALESCE(a.payroll_item_name, '')) NOT LIKE '%recovery%'
    GROUP BY p.payroll_year, p.payroll_month, p.payroll_half, a.employee_sk
),

att_emp AS (
    SELECT
        sa.processing_year                                      AS proc_year,
        sa.processing_month                                     AS proc_month,
        sa.processing_half                                      AS proc_half,
        e.employee_sk,
        SUM(CASE
            WHEN lower(COALESCE(sa.line_type_name, sa.line_type, '')) LIKE '%poya%'
            THEN COALESCE(sa.amount, 0) ELSE 0 END)             AS poya_day_wage,
        SUM(CASE
            WHEN lower(COALESCE(sa.line_type_name, sa.line_type, '')) LIKE '%sunday%'
            THEN COALESCE(sa.amount, 0) ELSE 0 END)             AS sunday_wage
    FROM {raw_schema}.stg_processed_sal_attendance sa
    INNER JOIN {mart_schema}.dim_employee e
        ON  e.source_emp_id = sa.source_emp_id
       AND e.tenant_id = sa.tenant_id
       AND e.is_current = true
    WHERE sa.tenant_id = '{tenant_id}'
      AND COALESCE(sa.amount, 0) <> 0
    GROUP BY sa.processing_year, sa.processing_month, sa.processing_half, e.employee_sk
),

ded_emp AS (
    SELECT
        p.payroll_year                                          AS proc_year,
        p.payroll_month                                         AS proc_month,
        p.payroll_half                                          AS proc_half,
        a.employee_sk,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%blend%recovery%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS blend_allowance_recovery,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%dollar%recovery%'
              OR lower(a.payroll_item_name) LIKE '%pegged%recovery%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS dollar_pegged_recovery,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%fuel%recovery%'
              OR lower(a.payroll_item_name) LIKE '%transport%recovery%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS fuel_transport_recovery,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%inflation%recovery%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS inflation_allowance_recovery,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%over time%recovery%'
              OR lower(a.payroll_item_name) LIKE '%ot%recovery%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS over_time_recovery,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%sales%recovery%'
              OR lower(a.payroll_item_name) LIKE '%incentive%recovery%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS sales_incentive_recovery,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%no pay%'
              OR lower(a.payroll_item_name) LIKE '%nopay%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS no_pay,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%salary advance%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS salary_advance,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%welfare%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS welfare_contribution,
        SUM(CASE
            WHEN lower(a.payroll_item_name) LIKE '%stamp%'
            THEN COALESCE(a.amount, 0) ELSE 0 END)              AS stamp_duty
    FROM {mart_schema}.fct_processed_add_ded a
    INNER JOIN {mart_schema}.dim_payroll_period p
        ON  p.payroll_period_sk = a.payroll_period_sk
       AND p.tenant_id = a.tenant_id
    WHERE a.tenant_id = '{tenant_id}'
      AND a.payroll_item_code IN ('2', '4')
      AND COALESCE(a.amount, 0) <> 0
    GROUP BY p.payroll_year, p.payroll_month, p.payroll_half, a.employee_sk
),

loan_emp AS (
    SELECT
        p.payroll_year                                          AS proc_year,
        p.payroll_month                                         AS proc_month,
        p.payroll_half                                          AS proc_half,
        l.employee_sk,
        SUM(CASE
            WHEN lower(COALESCE(l.deduction_name, '')) LIKE '%without%interest%'
            THEN COALESCE(l.installment_amount, 0) ELSE 0 END)    AS loan_without_interest,
        SUM(CASE
            WHEN lower(COALESCE(l.deduction_name, '')) NOT LIKE '%without%interest%'
            THEN COALESCE(l.installment_amount, 0) ELSE 0 END)    AS loan
    FROM {mart_schema}.fct_processed_loan_deduction l
    INNER JOIN {mart_schema}.dim_payroll_period p
        ON  p.payroll_period_sk = l.payroll_period_sk
       AND p.tenant_id = l.tenant_id
    WHERE l.tenant_id = '{tenant_id}'
      AND COALESCE(l.installment_amount, 0) <> 0
    GROUP BY p.payroll_year, p.payroll_month, p.payroll_half, l.employee_sk
),

bank_emp AS (
    SELECT
        p.payroll_year                                          AS proc_year,
        p.payroll_month                                         AS proc_month,
        p.payroll_half                                          AS proc_half,
        b.employee_sk,
        SUM(COALESCE(b.bank_amount, 0))                         AS total_bank_transferred
    FROM {mart_schema}.fct_salary_bank_instruction b
    INNER JOIN {mart_schema}.dim_payroll_period p
        ON  p.payroll_period_sk = b.payroll_period_sk
       AND p.tenant_id = b.tenant_id
    WHERE b.tenant_id = '{tenant_id}'
      AND COALESCE(b.bank_amount, 0) <> 0
    GROUP BY p.payroll_year, p.payroll_month, p.payroll_half, b.employee_sk
),

employee_wide AS (
    SELECT
        pc.proc_year,
        pc.proc_month,
        pc.proc_half,
        pc.je,
        pc.employee_sk,
        pc.emp_no,
        pc.basic_salary,
        COALESCE(a.fuel_transport_allowance, 0)               AS fuel_transport_allowance,
        COALESCE(a.inflation_allowance, 0)                      AS inflation_allowance,
        COALESCE(a.dollar_pegged, 0)                            AS dollar_pegged,
        COALESCE(a.car_allowance, 0)                            AS car_allowance,
        COALESCE(a.blend_allowance, 0)                          AS blend_allowance,
        COALESCE(a.cricket_allowance, 0)                        AS cricket_allowance,
        COALESCE(a.parent_child_benefit, 0)                     AS parent_child_benefit,
        COALESCE(a.annual_leave_encashment, 0)                  AS annual_leave_encashment,
        COALESCE(a.earn_leave_encashment, 0)                    AS earn_leave_encashment,
        COALESCE(a.inflation_allowance_arrears, 0)              AS inflation_allowance_arrears,
        COALESCE(a.night_allowance, 0)                          AS night_allowance,
        COALESCE(a.ot_arrears, 0)                               AS ot_arrears,
        pc.over_time,
        COALESCE(att.poya_day_wage, 0)                          AS poya_day_wage,
        COALESCE(a.salary_arrears, 0)                           AS salary_arrears,
        COALESCE(a.sales_incentive, 0)                          AS sales_incentive,
        COALESCE(att.sunday_wage, 0)                            AS sunday_wage,
        pc.epf_8,
        COALESCE(d.blend_allowance_recovery, 0)                 AS blend_allowance_recovery,
        COALESCE(d.dollar_pegged_recovery, 0)                   AS dollar_pegged_recovery,
        COALESCE(d.fuel_transport_recovery, 0)                    AS fuel_transport_recovery,
        COALESCE(d.inflation_allowance_recovery, 0)               AS inflation_allowance_recovery,
        COALESCE(l.loan, 0)                                     AS loan,
        COALESCE(l.loan_without_interest, 0)                    AS loan_without_interest,
        GREATEST(COALESCE(d.no_pay, 0), COALESCE(pc.no_pay_mart, 0))
                                                                AS no_pay,
        COALESCE(d.over_time_recovery, 0)                       AS over_time_recovery,
        COALESCE(d.sales_incentive_recovery, 0)                 AS sales_incentive_recovery,
        COALESCE(d.salary_advance, 0)                           AS salary_advance,
        COALESCE(d.welfare_contribution, 0)                     AS welfare_contribution,
        pc.apit,
        COALESCE(d.stamp_duty, 0)                               AS stamp_duty,
        pc.net_salary,
        COALESCE(b.total_bank_transferred, 0)                   AS total_bank_transferred,
        pc.epf_12,
        pc.etf_3
    FROM payroll_core pc
    LEFT JOIN add_emp a
        ON  a.proc_year = pc.proc_year
       AND a.proc_month = pc.proc_month
       AND a.proc_half = pc.proc_half
       AND a.employee_sk = pc.employee_sk
    LEFT JOIN att_emp att
        ON  att.proc_year = pc.proc_year
       AND att.proc_month = pc.proc_month
       AND att.proc_half = pc.proc_half
       AND att.employee_sk = pc.employee_sk
    LEFT JOIN ded_emp d
        ON  d.proc_year = pc.proc_year
       AND d.proc_month = pc.proc_month
       AND d.proc_half = pc.proc_half
       AND d.employee_sk = pc.employee_sk
    LEFT JOIN loan_emp l
        ON  l.proc_year = pc.proc_year
       AND l.proc_month = pc.proc_month
       AND l.proc_half = pc.proc_half
       AND l.employee_sk = pc.employee_sk
    LEFT JOIN bank_emp b
        ON  b.proc_year = pc.proc_year
       AND b.proc_month = pc.proc_month
       AND b.proc_half = pc.proc_half
       AND b.employee_sk = pc.employee_sk
),

employee_calc AS (
    SELECT
        ew.*,
        (
            ew.basic_salary
            + ew.fuel_transport_allowance
            + ew.inflation_allowance
            + ew.dollar_pegged
            + ew.car_allowance
            + ew.blend_allowance
            + ew.cricket_allowance
            + ew.parent_child_benefit
            + ew.annual_leave_encashment
            + ew.earn_leave_encashment
            + ew.inflation_allowance_arrears
            + ew.night_allowance
            + ew.ot_arrears
            + ew.over_time
            + ew.poya_day_wage
            + ew.salary_arrears
            + ew.sales_incentive
            + ew.sunday_wage
        )                                                       AS total_earnings_to_gross,
        ew.epf_8                                                AS contributions_from_gross,
        (
            ew.epf_8
            + ew.blend_allowance_recovery
            + ew.dollar_pegged_recovery
            + ew.fuel_transport_recovery
            + ew.inflation_allowance_recovery
            + ew.loan
            + ew.loan_without_interest
            + ew.no_pay
            + ew.over_time_recovery
            + ew.sales_incentive_recovery
        )                                                       AS total_deductions_from_gross,
        ew.salary_advance + ew.welfare_contribution             AS deductions_from_net,
        ew.apit + ew.stamp_duty                                 AS employee_total_taxes
    FROM employee_wide ew
),

je_summary AS (
    SELECT
        proc_year,
        proc_month,
        proc_half,
        je,
        COUNT(DISTINCT emp_no)                                  AS count_of_emp_no,
        ROUND(SUM(basic_salary)::numeric, 2)                    AS sum_of_basic_salary,
        ROUND(SUM(fuel_transport_allowance)::numeric, 2)          AS sum_of_fuel_transport_allowance,
        ROUND(SUM(inflation_allowance)::numeric, 2)             AS sum_of_inflation_allowance,
        ROUND(SUM(dollar_pegged)::numeric, 2)                     AS sum_of_dollar_pegged,
        ROUND(SUM(car_allowance)::numeric, 2)                     AS sum_of_car_allowance,
        ROUND(SUM(blend_allowance)::numeric, 2)                   AS sum_of_blend_allowance,
        ROUND(SUM(cricket_allowance)::numeric, 2)                 AS sum_of_cricket_allowance,
        ROUND(SUM(parent_child_benefit)::numeric, 2)              AS sum_of_parent_child_benefit,
        ROUND(SUM(annual_leave_encashment)::numeric, 2)           AS sum_of_annual_leave_encashment,
        ROUND(SUM(earn_leave_encashment)::numeric, 2)             AS sum_of_earn_leave_encashment,
        ROUND(SUM(inflation_allowance_arrears)::numeric, 2)        AS sum_of_inflation_allowance_arrears,
        ROUND(SUM(night_allowance)::numeric, 2)                   AS sum_of_night_allowance,
        ROUND(SUM(ot_arrears)::numeric, 2)                         AS sum_of_ot_arrears,
        ROUND(SUM(over_time)::numeric, 2)                         AS sum_of_over_time,
        ROUND(SUM(poya_day_wage)::numeric, 2)                     AS sum_of_poya_day_wage,
        ROUND(SUM(salary_arrears)::numeric, 2)                     AS sum_of_salary_arrears,
        ROUND(SUM(sales_incentive)::numeric, 2)                   AS sum_of_sales_incentive,
        ROUND(SUM(sunday_wage)::numeric, 2)                         AS sum_of_sunday_wage,
        ROUND(SUM(total_earnings_to_gross)::numeric, 2)           AS sum_of_total_earnings_to_gross,
        ROUND(SUM(contributions_from_gross)::numeric, 2)          AS sum_of_contributions_from_gross,
        ROUND(SUM(epf_8)::numeric, 2)                             AS sum_of_epf_8,
        ROUND(SUM(blend_allowance_recovery)::numeric, 2)            AS sum_of_blend_allowance_recovery,
        ROUND(SUM(dollar_pegged_recovery)::numeric, 2)             AS sum_of_dollar_pegged_recovery,
        ROUND(SUM(fuel_transport_recovery)::numeric, 2)             AS sum_of_fuel_transport_recovery,
        ROUND(SUM(inflation_allowance_recovery)::numeric, 2)        AS sum_of_inflation_allowance_recovery,
        ROUND(SUM(loan)::numeric, 2)                              AS sum_of_loan,
        ROUND(SUM(loan_without_interest)::numeric, 2)               AS sum_of_loan_without_interest,
        ROUND(SUM(no_pay)::numeric, 2)                            AS sum_of_no_pay,
        ROUND(SUM(over_time_recovery)::numeric, 2)                  AS sum_of_over_time_recovery,
        ROUND(SUM(sales_incentive_recovery)::numeric, 2)            AS sum_of_sales_incentive_recovery,
        ROUND(SUM(total_deductions_from_gross)::numeric, 2)         AS sum_of_total_deductions_from_gross,
        ROUND(SUM(total_earnings_to_gross - total_deductions_from_gross)::numeric, 2)
                                                                AS sum_of_total_gross_pay,
        ROUND(SUM(salary_advance)::numeric, 2)                      AS sum_of_salary_advance,
        ROUND(SUM(welfare_contribution)::numeric, 2)                AS sum_of_welfare_contribution,
        ROUND(SUM(deductions_from_net)::numeric, 2)               AS sum_of_deductions_from_net,
        ROUND(SUM(apit)::numeric, 2)                              AS sum_of_apit,
        ROUND(SUM(employee_total_taxes)::numeric, 2)              AS sum_of_employee_total_taxes,
        ROUND(SUM(stamp_duty)::numeric, 2)                        AS sum_of_stamp_duty,
        ROUND(SUM(net_salary)::numeric, 2)                          AS sum_of_net_pay,
        ROUND(SUM(total_bank_transferred)::numeric, 2)            AS sum_of_total_bank_transferred,
        ROUND(SUM(epf_12)::numeric, 2)                           AS sum_of_epf_12,
        ROUND(SUM(etf_3)::numeric, 2)                             AS sum_of_etf_3,
        1                                                         AS sort_order
    FROM employee_calc
    GROUP BY proc_year, proc_month, proc_half, je
),

grand_total AS (
    SELECT
        proc_year,
        proc_month,
        proc_half,
        'Grand Total'                                           AS je,
        SUM(count_of_emp_no)                                    AS count_of_emp_no,
        SUM(sum_of_basic_salary)                                AS sum_of_basic_salary,
        SUM(sum_of_fuel_transport_allowance)                      AS sum_of_fuel_transport_allowance,
        SUM(sum_of_inflation_allowance)                         AS sum_of_inflation_allowance,
        SUM(sum_of_dollar_pegged)                               AS sum_of_dollar_pegged,
        SUM(sum_of_car_allowance)                               AS sum_of_car_allowance,
        SUM(sum_of_blend_allowance)                             AS sum_of_blend_allowance,
        SUM(sum_of_cricket_allowance)                           AS sum_of_cricket_allowance,
        SUM(sum_of_parent_child_benefit)                        AS sum_of_parent_child_benefit,
        SUM(sum_of_annual_leave_encashment)                     AS sum_of_annual_leave_encashment,
        SUM(sum_of_earn_leave_encashment)                       AS sum_of_earn_leave_encashment,
        SUM(sum_of_inflation_allowance_arrears)                 AS sum_of_inflation_allowance_arrears,
        SUM(sum_of_night_allowance)                             AS sum_of_night_allowance,
        SUM(sum_of_ot_arrears)                                  AS sum_of_ot_arrears,
        SUM(sum_of_over_time)                                   AS sum_of_over_time,
        SUM(sum_of_poya_day_wage)                               AS sum_of_poya_day_wage,
        SUM(sum_of_salary_arrears)                              AS sum_of_salary_arrears,
        SUM(sum_of_sales_incentive)                             AS sum_of_sales_incentive,
        SUM(sum_of_sunday_wage)                                 AS sum_of_sunday_wage,
        SUM(sum_of_total_earnings_to_gross)                     AS sum_of_total_earnings_to_gross,
        SUM(sum_of_contributions_from_gross)                    AS sum_of_contributions_from_gross,
        SUM(sum_of_epf_8)                                       AS sum_of_epf_8,
        SUM(sum_of_blend_allowance_recovery)                    AS sum_of_blend_allowance_recovery,
        SUM(sum_of_dollar_pegged_recovery)                      AS sum_of_dollar_pegged_recovery,
        SUM(sum_of_fuel_transport_recovery)                     AS sum_of_fuel_transport_recovery,
        SUM(sum_of_inflation_allowance_recovery)                AS sum_of_inflation_allowance_recovery,
        SUM(sum_of_loan)                                        AS sum_of_loan,
        SUM(sum_of_loan_without_interest)                       AS sum_of_loan_without_interest,
        SUM(sum_of_no_pay)                                      AS sum_of_no_pay,
        SUM(sum_of_over_time_recovery)                          AS sum_of_over_time_recovery,
        SUM(sum_of_sales_incentive_recovery)                    AS sum_of_sales_incentive_recovery,
        SUM(sum_of_total_deductions_from_gross)                 AS sum_of_total_deductions_from_gross,
        SUM(sum_of_total_gross_pay)                             AS sum_of_total_gross_pay,
        SUM(sum_of_salary_advance)                              AS sum_of_salary_advance,
        SUM(sum_of_welfare_contribution)                        AS sum_of_welfare_contribution,
        SUM(sum_of_deductions_from_net)                         AS sum_of_deductions_from_net,
        SUM(sum_of_apit)                                        AS sum_of_apit,
        SUM(sum_of_employee_total_taxes)                        AS sum_of_employee_total_taxes,
        SUM(sum_of_stamp_duty)                                  AS sum_of_stamp_duty,
        SUM(sum_of_net_pay)                                     AS sum_of_net_pay,
        SUM(sum_of_total_bank_transferred)                      AS sum_of_total_bank_transferred,
        SUM(sum_of_epf_12)                                      AS sum_of_epf_12,
        SUM(sum_of_etf_3)                                       AS sum_of_etf_3,
        999                                                       AS sort_order
    FROM je_summary
    GROUP BY proc_year, proc_month, proc_half
)

SELECT * FROM je_summary
UNION ALL
SELECT * FROM grand_total
ORDER BY proc_year DESC, proc_month DESC, proc_half DESC, sort_order, je
