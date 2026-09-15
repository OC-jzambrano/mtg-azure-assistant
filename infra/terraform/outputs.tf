output "resource_group_name" {
  description = "Name of the created Azure Resource Group"
  value       = azurerm_resource_group.rg.name
}

output "acr_name" {
  description = "Name of the Azure Container Registry"
  value       = azurerm_container_registry.acr.name
}

output "acr_login_server" {
  description = "Login server hostname for Azure Container Registry"
  value       = azurerm_container_registry.acr.login_server
}

output "application_url" {
  description = "Public HTTPS URL for the MTG Call Center Assistant (FastAPI + /chat UI)"
  value       = "https://${azurerm_container_app.backend.latest_revision_fqdn}"
}

output "app_insights_connection_string" {
  description = "Application Insights connection string for OpenTelemetry runtime"
  value       = azurerm_application_insights.appinsights.connection_string
  sensitive   = true
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

output "managed_identity_client_id" {
  description = "Client ID of the User Assigned Identity for Container Apps"
  value       = azurerm_user_assigned_identity.ca_identity.client_id
}
