output "resource_group_name" {
  description = "Name of the created Resource Group"
  value       = azurerm_resource_group.rg.name
}

output "application_url" {
  description = "Public URL for the MTG Call Center Assistant API"
  value       = "https://${azurerm_container_app.backend.latest_revision_fqdn}"
}

output "app_insights_connection_string" {
  description = "Application Insights connection string for OpenTelemetry"
  value       = azurerm_application_insights.appinsights.connection_string
  sensitive   = true
}

output "azure_openai_endpoint" {
  description = "Azure OpenAI Service endpoint"
  value       = azurerm_cognitive_account.openai.endpoint
}

output "azure_openai_primary_key" {
  description = "Azure OpenAI primary access key (sensitive)"
  value       = azurerm_cognitive_account.openai.primary_access_key
  sensitive   = true
}

output "azure_openai_deployment_chat" {
  description = "Chat completion deployment name (gpt-4o-mini)"
  value       = azurerm_cognitive_deployment.gpt4o_mini.name
}

output "azure_openai_deployment_reasoning" {
  description = "Reasoning deployment name (gpt-4o)"
  value       = azurerm_cognitive_deployment.gpt4o.name
}

output "azure_openai_deployment_embeddings" {
  description = "Embedding deployment name (text-embedding-3-small)"
  value       = azurerm_cognitive_deployment.embeddings.name
}

output "key_vault_name" {
  description = "Name of the created Azure Key Vault"
  value       = azurerm_key_vault.kv.name
}

output "postgres_fqdn" {
  description = "PostgreSQL Flexible Server FQDN"
  value       = azurerm_postgresql_flexible_server.postgres.fqdn
}

output "postgres_database_name" {
  description = "Name of the created MTG database"
  value       = azurerm_postgresql_flexible_server_database.mtg_db.name
}

