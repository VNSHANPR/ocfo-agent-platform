# Supervisor — Terraform (the CI/CD path for the Multi-Agent Supervisor)

DABs has no resource for the Agent Bricks Multi-Agent Supervisor, so its lifecycle is
managed here with the **`databricks_supervisor_agent`** Terraform resource. This runs
**after** `databricks bundle deploy/run` (which creates the Genie spaces, metric views
and UC-function tools).

## Pipeline order (per environment)
```bash
# 1) data + genie + tools via DABs
databricks bundle deploy --target dev --profile fevm-de-cert-classic
databricks bundle run ocfo_agent_platform_deploy --target dev --profile fevm-de-cert-classic

# 2) supervisor via Terraform
cd terraform
cp terraform.tfvars.example terraform.tfvars   # fill genie ids from step 1 / ka_tile_id
terraform init
terraform plan
terraform apply

# 3) Phase-7 quality gate: run the MLflow eval notebook against the endpoint
terraform output endpoint_name        # -> point the eval notebook here
```

In CI (GitHub Actions), authenticate the provider with `DATABRICKS_HOST` + `DATABRICKS_TOKEN`
(or OAuth) env vars and leave `profile = ""`; store Terraform state in a remote backend.

## Current limitation (important)
The `databricks_supervisor_agent` resource today exposes `display_name`, `description`,
`instructions` and `provider_config`, and **exports** `endpoint_name`, `experiment_id` and
`supervisor_agent_id`. It does **not yet expose sub-agent / tool blocks**. So Terraform:
- creates and version-controls the **supervisor and its routing instructions**, and
- gives CI/CD its **endpoint + experiment id** for the eval gate.

The **sub-agents/tools** (the 4 Genie spaces, the Knowledge Assistant, the UC-function
tools) are attached **once via the Agent Bricks UI/SDK**. Their ids are declared in
`main.tf` (`locals.subagents` / `locals.uc_function_tools`) and `variables.tf`, so they're
version-controlled and ready to wire into the resource as soon as the provider adds
subagent arguments.

## Files
- `main.tf` — provider + `databricks_supervisor_agent` + versioned instructions + subagent/tool refs
- `variables.tf` — profile, supervisor name, catalog, Genie ids, KA tile id
- `outputs.tf` — `supervisor_agent_id`, `endpoint_name`, `experiment_id`
- `terraform.tfvars.example` — per-environment values
