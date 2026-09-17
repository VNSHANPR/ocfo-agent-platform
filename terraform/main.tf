# ============================================================
# oCFO Enterprise Supervisor — managed as code with Terraform.
#
# DABs has no resource for the Agent Bricks Multi-Agent Supervisor, so the
# supervisor's lifecycle + instructions are managed here with the
# `databricks_supervisor_agent` resource. Run this AFTER `databricks bundle
# deploy/run` (which creates the Genie spaces, metric views and UC tools).
#
# NOTE (provider limitation, as of this writing): the resource exposes
# display_name / description / instructions / provider_config and exports the
# serving endpoint + MLflow experiment id. It does NOT yet expose sub-agent /
# tool blocks, so the Genie spaces, Knowledge Assistant and UC-function tools
# are attached once via the Agent Bricks UI/SDK (see terraform/README.md).
# Their ids are declared below so they're version-controlled and ready to wire
# in as soon as the provider supports subagent arguments.
# ============================================================

terraform {
  required_providers {
    databricks = {
      source  = "databricks/databricks"
      version = ">= 1.0" # use a recent release that includes databricks_supervisor_agent
    }
  }
}

# Auth: locally via `profile`; in CI via env vars DATABRICKS_HOST / DATABRICKS_TOKEN
# (or OAuth) — leave `profile` unset in CI.
provider "databricks" {
  profile = var.profile != "" ? var.profile : null
}

locals {
  # Single source of truth for the routing policy (kept in sync with
  # ../config/supervisor_instructions.yml used by the DABs notebook path).
  instructions = <<-EOT
    You are the oCFO Enterprise Supervisor for Flight Centre Travel Group. Route each
    question to the single most appropriate specialist agent based on its domain.

    Routing rules:
    1. Use office_of_cfo for group financials: P&L, TTV, revenue, margin, EBITDA, NPAT,
       cash, working capital (DSO/DPO/DIO/CCC), FX and regional performance.
    2. Use hr_workforce for headcount, hiring, attrition, tenure and compensation.
    3. Use travel_expense for employee travel/expense spend, out-of-policy spend and merchants.
    4. Use supplier_procurement for supplier spend, savings, contracts and supplier risk.
    5. Use financial_results_docs for questions grounded in published results documents.
    6. Use the calculation tools (fx_convert, cash_conversion_cycle, fctg_fiscal_period,
       pct_change) only for explicit computations the data agents do not already return.
    7. Call multiple agents only when the question genuinely spans domains.
    8. Do not call an agent merely to confirm information already established.
    9. If the question is ambiguous, ask one concise clarification question.
    10. Never invent a result when a sub-agent returns no answer.
    11. In the final response, identify which domains contributed to the answer.
  EOT

  # Sub-agents & tools to attach (version-controlled; wired via UI/SDK until the
  # provider exposes subagent blocks). Genie ids come from the DABs deploy.
  subagents = {
    office_of_cfo        = { kind = "genie", ref = var.genie_ocfo }
    hr_workforce         = { kind = "genie", ref = var.genie_hr }
    travel_expense       = { kind = "genie", ref = var.genie_concur }
    supplier_procurement = { kind = "genie", ref = var.genie_ariba }
    financial_results    = { kind = "knowledge_assistant", ref = var.ka_tile_id }
  }
  uc_function_tools = [
    "${var.catalog}.agent_tools.fx_convert",
    "${var.catalog}.agent_tools.cash_conversion_cycle",
    "${var.catalog}.agent_tools.fctg_fiscal_period",
    "${var.catalog}.agent_tools.pct_change",
  ]
}

resource "databricks_supervisor_agent" "ocfo" {
  display_name = var.supervisor_name
  description  = "Enterprise supervisor routing across oCFO finance, HR (Workday), travel (Concur) and supplier (Ariba) Genie agents, a financial-results Knowledge Assistant, and governed UC-function tools."
  instructions = local.instructions
}
