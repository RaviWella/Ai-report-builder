# Payroll Lineage

MintHRM processed payroll → warehouse marts.

## Processed payroll facts

```text
processed_sal_basic_data
  ↓
stg_payroll_details
  ↓
stg_processed_sal_basic_data (dbt view)
  ↓
fct_processed_salary
  ↓
mart_processed_payroll_summary
  ↓
vw_payroll_summary
```

```text
processed_sal_add_ded
  ↓
stg_payroll_add_ded
  ↓
fct_processed_add_ded
  ↓
mart_horizontal_paysheet_dynamic
```

```text
processed_tax_data_for_employee
  ↓
stg_payroll_tax
  ↓
fct_processed_tax
  ↓
mart_statutory_summary
```

```text
prl_salary_retrieve + prl_salary_bank_data
  ↓
stg_payroll_salary_retrieve / stg_payroll_salary_bank_data
  ↓
fct_salary_bank_instruction
```

## Source alias map (dbt)

| MintHRM logical name | hr_raw staging |
|----------------------|----------------|
| `bank` | `stg_payroll_bank` |
| `hr_payroll_groups` | `raw_hr_payroll_groups` |
| `mas_branch` | `stg_payroll_bank_branch` |
| `prl_loan` | `stg_prl_loan` |
| `prl_processed_nonecash_benefits` | `stg_payroll_noncash_benefits` |
| `prl_processed_salary_analyze` | `stg_payroll_salary_analyze` |
| `prl_salary_bank_data` | `stg_payroll_salary_bank_data` |
| `prl_salary_retrieve` | `stg_payroll_salary_retrieve` |
| `prl_variableadditions_forsal` | `stg_payroll_variable_additions` |
| `prl_variabledeductions_forsal` | `stg_payroll_variable_deductions` |
| `processed_installment_payment_data` | `stg_payroll_installment_payments` |
| `processed_loan_data` | `stg_payroll_loan_data` |
| `processed_multi_currency_for_emp_sal` | `stg_payroll_multi_currency` |
| `processed_non_consider_pay_items` | `stg_payroll_non_consider_items` |
| `processed_sal_add_ded` | `stg_payroll_add_ded` |
| `processed_sal_attendance` | `stg_payroll_attendance_lines` |
| `processed_sal_attendance_compliance` | `stg_payroll_compliance_attendance` |
| `processed_sal_basic_data` | `stg_payroll_details` |
| `processed_sal_basic_data_compliance` | `stg_payroll_compliance_basic` |
| `processed_tax_data_for_employee` | `stg_payroll_tax` |
