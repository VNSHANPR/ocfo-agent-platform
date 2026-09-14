# oCFO Agent Platform — consolidated DABs project

Ships the **entire agentic stack** for the Office-of-the-CFO demo as Infrastructure-as-Code,
so it promotes cleanly across **dev → preprod → prod** workspaces from one project.

## What it deploys

| Layer | Contents |
|-------|----------|
| **Data layer** | `agent_tools` UC functions (`fx_convert`, `cash_conversion_cycle`, `fctg_fiscal_period`, `pct_change`) + 6 certified metric views (oCFO, HR, Concur, Ariba) |
| **Genie layer** | 4 curated Genie spaces declared as **native `genie_spaces` DABs resources** (engine: `direct`), each backed by a versioned `*.geniespace.json` |
| **Supervisor** | Multi-Agent Supervisor wiring the 4 Genie spaces + the Knowledge Assistant (as a direct subagent) + the UC-function tools, with routing rules & examples |

```
databricks.yml                       # bundle (engine: direct), variables, native genie_spaces resources, dev/preprod/prod targets
config/supervisor_instructions.yml   # master prompt + routing rules + agent descriptions + examples (versioned)
genie/*.geniespace.json              # versioned serialized definition for each Genie space (file_path of each genie_spaces resource)
src/deploy_data_layer.py             # UC functions + metric views (catalog-parameterized, idempotent)
src/create_supervisor.py             # assemble + create/update the supervisor from config + resolved genie ids + KA
resources/ocfo_platform.job.yml      # job: data layer → supervisor (Genie spaces deploy declaratively)
# fallback (older CLIs only):
genie/manifest.json.fallback         # key → title/description/file map
src/deploy_genie_spaces.py           # notebook that create-or-updates Genie spaces via REST when genie_spaces isn't supported
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
- **Genie spaces are native `genie_spaces` DABs resources** under the `direct` engine — they
  deploy with `bundle deploy` and the supervisor step reads their ids via
  `${resources.genie_spaces.<key>.id}`. This requires a **recent Databricks CLI**; on older
  CLIs (e.g. v1.0.0) `bundle validate` reports `unknown field: genie_spaces`. In that case,
  remove the `genie_spaces` block + `engine: direct`, and run the fallback notebook
  `src/deploy_genie_spaces.py` (add it back as the first job task) which create-or-updates the
  spaces via `/api/2.0/genie/spaces`.
- The Multi-Agent Supervisor is the **managed Agent Bricks MAS** (there is no native DABs
  resource for it); `create_supervisor.py` creates it via the Agent Bricks API when available,
  otherwise prints the resolved spec for one-time UI creation. MLflow tracing + evaluation of
  the supervisor is a companion notebook.
