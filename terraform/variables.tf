variable "profile" {
  description = "Databricks CLI profile for local runs. Leave empty in CI (use DATABRICKS_HOST/DATABRICKS_TOKEN env vars)."
  type        = string
  default     = ""
}

variable "supervisor_name" {
  description = "Display name of the Multi-Agent Supervisor (unique per workspace)."
  type        = string
  default     = "oCFO Enterprise Supervisor"
}

variable "catalog" {
  description = "Unity Catalog holding the agent_tools functions for this environment."
  type        = string
  default     = "de_cert_classic_catalog"
}

# Sub-agent references — set per environment (from the DABs-created Genie spaces).
variable "genie_ocfo" {
  type    = string
  default = ""
}
variable "genie_hr" {
  type    = string
  default = ""
}
variable "genie_concur" {
  type    = string
  default = ""
}
variable "genie_ariba" {
  type    = string
  default = ""
}
variable "ka_tile_id" {
  description = "Knowledge Assistant tile id for the financial-results docs subagent."
  type        = string
  default     = ""
}
