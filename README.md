# oCFO Agent Platform — consolidated DABs project

Ships the **entire agentic stack** for the Office-of-the-CFO demo as Infrastructure-as-Code,
so it promotes cleanly across **dev → preprod → prod** workspaces from one project.

## What it deploys

| Layer | Contents |
|-------|----------|
| **Data layer** | `agent_tools` UC functions (`fx_convert`, `cash_conversion_cycle`, `fctg_fiscal_period`, `pct_change`) + 6 certified metric views (oCFO, HR, Concur, Ariba) |
| **Genie layer** | 4 curated Genie spaces created from versioned `serialized_space` JSON (oCFO, HR/Workday, Concur, Ariba) |
| **Supervisor** | Multi-Agent Supervisor wiring the 4 Genie spaces + the Knowledge Assistant (as a direct subagent) + the UC-function tools, with routing rules & examples |

```
databricks.yml                       # bundle, variables, dev/preprod/prod targets
config/supervisor_instructions.yml   # master prompt + routing rules + agent descriptions + examples (versioned)
genie/manifest.json                  # key → title/description/file for each Genie space
genie/genie_*.json                   # exported serialized_space for each space (IaC)
src/deploy_data_layer.py             # UC functions + metric views (catalog-parameterized, idempotent)
src/deploy_genie_spaces.py           # create-or-update Genie spaces from JSON, remap catalog, emit ids
src/create_supervisor.py             # assemble + create/update the supervisor from config + ids + KA
resources/ocfo_platform.job.yml      # job: data layer → genie spaces → supervisor
```

## Promotion model

Everything is catalog-parameterized. A deploy to another environment:
1. sets `catalog` (and `source_catalog` for the Genie catalog remap) for that workspace,
2. rebuilds the data layer, re-creates/updates the Genie spaces there,
3. re-creates/updates the supervisor pointing at that environment's spaces.

The Genie `serialized_space` JSON is the source of truth — edit a space, re-export it into
`genie/`, commit, and every environment converges on redeploy.

## Deploy

```bash
databricks bundle validate --target dev
databricks bundle deploy   --target dev
databricks bundle run ocfo_agent_platform_deploy --target dev
# promote:
databricks bundle deploy --target preprod && databricks bundle run ocfo_agent_platform_deploy --target preprod
databricks bundle deploy --target prod    && databricks bundle run ocfo_agent_platform_deploy --target prod
```

## Prerequisites per environment
- Source tables in `<catalog>.office_of_cfo`, `.workday_hr`, `.concur_spend`, `.ariba_supplier`.
- A Knowledge Assistant over the financial-results volume; set its tile id via the
  `ka_tile_id` bundle variable so it's wired in as a subagent.
- A SQL warehouse id in `warehouse_id`.

## Notes
- No native DABs resource exists for Genie spaces, so they are deployed via the
  serialized-JSON + `/api/2.0/genie/spaces` create-or-update pattern in `deploy_genie_spaces.py`.
- The programmatic Multi-Agent Supervisor API (Agent Bricks) is used when available in the
  target workspace; otherwise `create_supervisor.py` prints the resolved spec for one-time
  UI creation. MLflow tracing + evaluation of the supervisor is a companion notebook.
