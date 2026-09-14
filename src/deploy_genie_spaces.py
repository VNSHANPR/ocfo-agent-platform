# Databricks notebook source
# MAGIC %md
# MAGIC # (FALLBACK) Deploy Genie spaces from versioned serialized_space JSON
# MAGIC **Only needed on CLIs that don't yet support the native `genie_spaces` DABs resource.**
# MAGIC The primary path declares Genie spaces natively in `databricks.yml` (engine: direct) and
# MAGIC `bundle deploy` creates them. Use this notebook instead if your CLI reports
# MAGIC "unknown field: genie_spaces": create-or-update each space from `genie/*.geniespace.json`,
# MAGIC remap the source catalog, and emit a key→space_id map as a task value.
# MAGIC (Reads genie/manifest.json.fallback.)

# COMMAND ----------
# MAGIC %pip install -U databricks-sdk
# MAGIC %restart_python

# COMMAND ----------
import os, json
from databricks.sdk import WorkspaceClient

dbutils.widgets.text("catalog", "de_cert_classic_catalog")
dbutils.widgets.text("source_catalog", "de_cert_classic_catalog")
dbutils.widgets.text("warehouse_id", "")
dbutils.widgets.text("genie_parent_path", "/Workspace/Shared/ocfo_agent_platform/genie_spaces")
CAT = dbutils.widgets.get("catalog")
SRC = dbutils.widgets.get("source_catalog")
WH  = dbutils.widgets.get("warehouse_id")
PARENT = dbutils.widgets.get("genie_parent_path")

w = WorkspaceClient()
try:
    w.workspace.mkdirs(PARENT)
except Exception as e:
    print("mkdirs:", e)

# Locate the bundled genie folder (../genie relative to this notebook).
base = os.path.dirname(os.path.abspath("__file__"))
gdir = os.path.join(base, "..", "genie")
if not os.path.isdir(gdir):
    gdir = "../genie"
manifest = json.load(open(os.path.join(gdir, "manifest.json.fallback")))

# Existing spaces by title (create-or-update).
existing = {s["title"]: s["space_id"] for s in
            (w.api_client.do("GET", "/api/2.0/genie/spaces").get("spaces") or [])}

genie_ids = {}
for sp in manifest["spaces"]:
    ss = open(os.path.join(gdir, sp["file"])).read()
    if SRC != CAT:
        ss = ss.replace(SRC, CAT)  # remap catalog for this environment
    title = sp["title"]
    if title in existing:
        sid = existing[title]
        w.api_client.do("PATCH", f"/api/2.0/genie/spaces/{sid}", body={"serialized_space": ss})
        print("updated", title, sid)
    else:
        body = {"warehouse_id": WH, "title": title, "description": sp["description"],
                "parent_path": PARENT, "serialized_space": ss}
        res = w.api_client.do("POST", "/api/2.0/genie/spaces", body=body)
        sid = res.get("space_id") or res.get("id")
        print("created", title, sid)
    genie_ids[sp["key"]] = sid

dbutils.jobs.taskValues.set(key="genie_ids", value=json.dumps(genie_ids))
print("genie_ids:", genie_ids)
