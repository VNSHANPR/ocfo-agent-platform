# Databricks notebook source
# MAGIC %md
# MAGIC # Deploy the data layer — UC function tools + certified metric views
# MAGIC Idempotent. Catalog-parameterized so it promotes across environments.

# COMMAND ----------
dbutils.widgets.text("catalog", "de_cert_classic_catalog")
CAT = dbutils.widgets.get("catalog")
spark.sql(f"USE CATALOG {CAT}")
spark.sql("CREATE SCHEMA IF NOT EXISTS agent_tools COMMENT 'Tools exposed to the Multi-Agent Supervisor.'")

# COMMAND ----------
# ---- UC function tools ----
funcs = [
f"""CREATE OR REPLACE FUNCTION {CAT}.agent_tools.fx_convert(amount DOUBLE COMMENT 'Amount in source currency', from_ccy STRING COMMENT 'Source ISO code e.g. AUD', to_ccy STRING COMMENT 'Target ISO code e.g. USD')
RETURNS DOUBLE LANGUAGE PYTHON
COMMENT 'Convert an amount between currencies using indicative static rates (AUD, USD, EUR, GBP, SGD, NZD).'
AS $$
    rates={{"USD":1.0,"AUD":0.66,"EUR":1.08,"GBP":1.27,"SGD":0.74,"NZD":0.61}}
    f=rates.get((from_ccy or '').upper()); t=rates.get((to_ccy or '').upper())
    return None if (amount is None or not f or not t) else round(amount*f/t,2)
$$""",
f"""CREATE OR REPLACE FUNCTION {CAT}.agent_tools.cash_conversion_cycle(dso DOUBLE COMMENT 'Days Sales Outstanding', dio DOUBLE COMMENT 'Days Inventory Outstanding', dpo DOUBLE COMMENT 'Days Payable Outstanding')
RETURNS DOUBLE LANGUAGE PYTHON
COMMENT 'Cash Conversion Cycle = DSO + DIO - DPO (days).'
AS $$
    return None if None in (dso,dio,dpo) else round(dso+dio-dpo,1)
$$""",
f"""CREATE OR REPLACE FUNCTION {CAT}.agent_tools.fctg_fiscal_period(d DATE COMMENT 'A calendar date')
RETURNS STRING LANGUAGE PYTHON
COMMENT 'Map a date to the FCTG fiscal period (FY ends 30 June), e.g. FY26 Q1.'
AS $$
    if d is None: return None
    y,m=d.year,d.month; fy=y+1 if m>=7 else y
    q={{7:1,8:1,9:1,10:2,11:2,12:2,1:3,2:3,3:3,4:4,5:4,6:4}}[m]
    return f'FY{{str(fy)[-2:]}} Q{{q}}'
$$""",
f"""CREATE OR REPLACE FUNCTION {CAT}.agent_tools.pct_change(old_value DOUBLE COMMENT 'Prior value', new_value DOUBLE COMMENT 'Current value')
RETURNS DOUBLE LANGUAGE PYTHON
COMMENT 'Percentage change 100*(new-old)/old, 1 dp.'
AS $$
    return None if (old_value in (None,0) or new_value is None) else round(100.0*(new_value-old_value)/old_value,1)
$$""",
]
for f in funcs:
    spark.sql(f); print("function OK")

# COMMAND ----------
# ---- Certified metric views (catalog-parameterized) ----
def mv(name, yaml_body):
    spark.sql(f"CREATE OR REPLACE VIEW {CAT}.{name} WITH METRICS LANGUAGE YAML AS $${yaml_body}$$")
    print("metric view OK:", name)

mv("office_of_cfo.mv_group_pnl", f"""
version: 1.1
comment: "Group P&L by fiscal year."
source: {CAT}.office_of_cfo.group_pnl
dimensions:
  - name: Fiscal Year
    expr: fiscal_year
measures:
  - name: TTV
    expr: SUM(ttv)
  - name: Revenue
    expr: SUM(revenue)
  - name: EBITDA
    expr: SUM(ebitda)
  - name: Underlying NPAT
    expr: SUM(underlying_npat)
  - name: Revenue Margin %
    expr: SUM(revenue) / NULLIF(SUM(ttv),0) * 100
""")

mv("office_of_cfo.mv_working_capital", f"""
version: 1.1
comment: "Working-capital KPIs (DSO/DPO/DIO/CCC) by month."
source: {CAT}.office_of_cfo.working_capital_monthly
dimensions:
  - name: Month
    expr: month
  - name: Month Index
    expr: month_idx
measures:
  - name: Avg DSO
    expr: AVG(dso)
  - name: Avg DPO
    expr: AVG(dpo)
  - name: Avg DIO
    expr: AVG(dio)
  - name: Avg CCC
    expr: AVG(ccc)
""")

mv("workday_hr.mv_headcount", f"""
version: 1.1
comment: "Headcount, hiring and attrition by month/department/region."
source: {CAT}.workday_hr.headcount_monthly
dimensions:
  - name: Month
    expr: month
  - name: Department
    expr: department
  - name: Region
    expr: region
measures:
  - name: Headcount
    expr: SUM(headcount)
  - name: Hires
    expr: SUM(hires)
  - name: Terminations
    expr: SUM(terminations)
  - name: Avg Attrition Rate %
    expr: AVG(attrition_rate_pct)
  - name: Open Requisitions
    expr: SUM(open_requisitions)
""")

mv("workday_hr.mv_compensation", f"""
version: 1.1
comment: "Headcount-weighted compensation by department and job level."
source: {CAT}.workday_hr.compensation_by_level
dimensions:
  - name: Department
    expr: department
  - name: Job Level
    expr: job_level
measures:
  - name: Headcount
    expr: SUM(headcount)
  - name: Avg Total Comp
    expr: SUM(avg_total_comp_usd * headcount) / NULLIF(SUM(headcount),0)
""")

mv("concur_spend.mv_travel_spend", f"""
version: 1.1
comment: "Travel & expense spend with out-of-policy rate."
source: {CAT}.concur_spend.travel_spend_monthly
dimensions:
  - name: Month
    expr: CAST(month AS DATE)
  - name: Category
    expr: category
  - name: Region
    expr: region
measures:
  - name: Total Spend
    expr: SUM(total_spend_usd)
  - name: Out of Policy Spend
    expr: SUM(out_of_policy_spend_usd)
  - name: Out of Policy %
    expr: SUM(out_of_policy_spend_usd) / NULLIF(SUM(total_spend_usd),0) * 100
  - name: Transactions
    expr: SUM(transaction_count)
""")

mv("ariba_supplier.mv_supplier_spend", f"""
version: 1.1
comment: "Supplier spend, savings and risk."
source: {CAT}.ariba_supplier.supplier_spend_monthly
joins:
  - name: supplier
    source: {CAT}.ariba_supplier.suppliers
    on: source.supplier_id = supplier.supplier_id
dimensions:
  - name: Month
    expr: source.month
  - name: Category
    expr: source.category
  - name: Region
    expr: supplier.region
  - name: Risk Tier
    expr: supplier.risk_tier
  - name: Supplier
    expr: supplier.supplier_name
measures:
  - name: Spend
    expr: SUM(source.spend_usd)
  - name: Realized Savings
    expr: SUM(source.savings_usd)
  - name: Savings %
    expr: SUM(source.savings_usd) / NULLIF(SUM(source.spend_usd),0) * 100
""")

print("Data layer deployed to", CAT)
