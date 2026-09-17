# Databricks notebook source
# MAGIC %md
# MAGIC # Create / update the Multi-Agent Supervisor (via the /api/2.1 REST API)
# MAGIC Creates the supervisor and attaches its sub-agents/tools — the 4 Genie spaces, the
# MAGIC Knowledge Assistant, and the UC-function tools — using the Agent Bricks REST API.
# MAGIC Idempotent: re-uses the supervisor by display_name and only attaches missing tools.
# MAGIC Runs from the bundle job after the data layer + Genie spaces are deployed.

# COMMAND ----------
# MAGIC %pip install -U databricks-sdk pyyaml
# MAGIC %restart_python

# COMMAND ----------
import os, json, yaml
from databricks.sdk import WorkspaceClient

for _w in ("catalog", "supervisor_name", "ka_tile_id",
           "genie_ocfo", "genie_hr", "genie_concur", "genie_ariba"):
    dbutils.widgets.text(_w, "")
CAT  = dbutils.widgets.get("catalog") or "de_cert_classic_catalog"
NAME = dbutils.widgets.get("supervisor_name") or "oCFO Enterprise Supervisor"
KA   = dbutils.widgets.get("ka_tile_id")
GENIE = {
    "ocfo":   dbutils.widgets.get("genie_ocfo"),
    "hr":     dbutils.widgets.get("genie_hr"),
    "concur": dbutils.widgets.get("genie_concur"),
    "ariba":  dbutils.widgets.get("genie_ariba"),
}

w = WorkspaceClient()
def api(method, path, body=None, query=None):
    return w.api_client.do(method, path, body=body, query=query)

# COMMAND ----------
# Load the versioned instructions + agent/tool config.
base = os.path.dirname(os.path.abspath("__file__"))
cfg_path = os.path.join(base, "..", "config", "supervisor_instructions.yml")
if not os.path.exists(cfg_path):
    cfg_path = "../config/supervisor_instructions.yml"
cfg = yaml.safe_load(open(cfg_path))
instructions = cfg["instructions"]

# COMMAND ----------
# 1) Create-or-reuse the supervisor (body is UNWRAPPED — fields at top level).
existing = {s.get("display_name"): s for s in
            (api("GET", "/api/2.1/supervisor-agents").get("supervisor_agents") or [])}
if NAME in existing:
    sup = existing[NAME]
    sid = sup.get("supervisor_agent_id")
    api("PATCH", f"/api/2.1/supervisor-agents/{sid}",
        body={"display_name": NAME, "instructions": instructions})
    print("reusing supervisor:", sid)
else:
    sup = api("POST", "/api/2.1/supervisor-agents",
              body={"display_name": NAME,
                    "description": "Routes across oCFO finance, HR, Travel and Supplier Genie agents, a financial-results Knowledge Assistant, and governed UC-function tools.",
                    "instructions": instructions})
    sid = sup.get("supervisor_agent_id")
    print("created supervisor:", sid)
print("endpoint:", sup.get("endpoint_name"), "| experiment:", sup.get("experiment_id"))

# COMMAND ----------
# 2) Build the desired tool set from config + resolved ids.
tools = []
for a in cfg["agents"]:
    d = " ".join(a["description"].split())
    if a["kind"] == "genie":
        gid = GENIE.get(a["key"])
        if gid:
            tools.append((a["name"], {"tool_type": "genie_space", "genie_space": {"id": gid}, "description": d}))
    elif a["kind"] == "knowledge_assistant" and KA:
        tools.append((a["name"], {"tool_type": "knowledge_assistant",
                                  "knowledge_assistant": {"knowledge_assistant_id": KA}, "description": d}))
for t in cfg.get("uc_function_tools", []):
    nm = t["name"].split(".")[-1]
    tools.append((nm, {"tool_type": "uc_function",
                       "uc_function": {"name": f'{CAT}.{t["name"]}'}, "description": t["description"]}))

# 3) Attach only the tools not already present (idempotent).
have = {t.get("tool_id") for t in (api("GET", f"/api/2.1/supervisor-agents/{sid}/tools").get("tools") or [])}
for tool_id, tool in tools:
    if tool_id in have:
        print("  exists  ", tool_id); continue
    try:
        api("POST", f"/api/2.1/supervisor-agents/{sid}/tools", body=tool, query={"tool_id": tool_id})
        print("  attached", tool_id)
    except Exception as e:
        print("  FAILED  ", tool_id, str(e)[:180])

# COMMAND ----------
final = api("GET", f"/api/2.1/supervisor-agents/{sid}/tools").get("tools") or []
print(f"Supervisor '{NAME}' ({sid}) now has {len(final)} tools:")
for t in final:
    print("  -", t.get("tool_id"), "|", t.get("tool_type"))
