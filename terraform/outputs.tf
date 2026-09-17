# These outputs feed the Phase-7 MLflow evaluation notebook.
output "supervisor_agent_id" {
  description = "UUID of the Supervisor Agent."
  value       = databricks_supervisor_agent.ocfo.supervisor_agent_id
}

output "endpoint_name" {
  description = "Serving endpoint name — point the MLflow eval notebook at this."
  value       = databricks_supervisor_agent.ocfo.endpoint_name
}

output "experiment_id" {
  description = "MLflow experiment id for the supervisor's traces/evaluation."
  value       = databricks_supervisor_agent.ocfo.experiment_id
}
