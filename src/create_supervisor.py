# Databricks notebook source
# MAGIC %md
# MAGIC # Create / update the Multi-Agent Supervisor
# MAGIC Reads the versioned instructions, the Genie ids from the upstream task, and the
# MAGIC KA tile id, then assembles + creates/updates the supervisor (KA is a direct subagent).

# COMMAND ----------
# MAGIC %pip install -U databricks-sdk pyyaml
# MAGIC %restart_python

# COMMAND ----------
import os, json, yaml

dbutils.widgets.text("catalog", "de_cert_classic_catalog")
dbutils.widgets.text("supervisor_name", "oCFO Enterprise Supervisor")
dbutils.widgets.text("ka_tile_id", "")
CAT   = dbutils.widgets.get("catalog")
NAME  = dbutils.widgets.get("supervisor_name")
KA    = dbutils.widgets.get("ka_tile_id")

# Genie ids from the upstream deploy_genie_spaces task.
try:
    genie_ids = json.loads(dbutils.jobs.taskValues.get(taskKey="deploy_genie_spaces", key="genie_ids"))
except Exception as e:
    print("no upstream genie_ids task value:", e); genie_ids = {}

base = os.path.dirname(os.path.abspath("__file__"))
cfg_path = os.path.join(base, "..", "config", "supervisor_instructions.yml")
if not os.path.exists(cfg_path): cfg_path = "../config/supervisor_instructions.yml"
cfg = yaml.safe_load(open(cfg_path))

# COMMAND ----------
agents = []
for a in cfg["agents"]:
    d = " ".join(a["description"].split())
    if a["kind"] == "genie":
        sid = genie_ids.get(a["key"])
        if not sid: print("skip", a["name"], "(no genie id)"); continue
        agents.append({"name": a["name"], "description": d, "genie_space_id": sid})
    elif a["kind"] == "knowledge_assistant":
        if not KA: print("skip", a["name"], "(no ka_tile_id set)"); continue
        agents.append({"name": a["name"], "description": d, "ka_tile_id": KA})

for t in cfg.get("uc_function_tools", []):
    agents.append({"name": t["name"].split(".")[-1],
                   "uc_function_name": f'{CAT}.{t["name"]}',
                   "description": t["description"]})

spec = {"name": NAME, "instructions": cfg["instructions"], "agents": agents,
        "examples": [{"question": e["question"], "guideline": e["guideline"]}
                     for e in cfg.get("routing_examples", [])]}
print(json.dumps(spec, indent=2))

# COMMAND ----------
created = False
try:
    from databricks_ai_bridge.agent_bricks import manage_mas  # type: ignore
    res = manage_mas(action="create_or_update", name=spec["name"], agents=spec["agents"],
                     description="oCFO enterprise supervisor", instructions=spec["instructions"],
                     examples=spec["examples"])
    print("Supervisor created/updated:", res); created = True
except Exception as e:
    print(f"Programmatic MAS API not available here ({type(e).__name__}: {e}).")

if not created:
    print("\n=== Create in Agent Bricks UI with the spec above ===")
    print("Agents → Agent Bricks → Multi-Agent Supervisor → Create; add each agent (Genie id /")
    print("KA tile id / UC function) with its description, paste the instructions, add examples, deploy.")
