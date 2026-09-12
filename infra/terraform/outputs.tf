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

output "postgres_fqdn" {
  description = "PostgreSQL Flexible Server FQDN"
  value       = azurerm_postgresql_flexible_server.postgres.fqdn
}

output "postgres_database_name" {
  description = "Name of the created MTG database"
  value       = azurerm_postgresql_flexible_server_database.mtg_db.name
}

output "redis_hostname" {
  description = "Azure Cache for Redis hostname"
  value       = azurerm_redis_cache.redis.hostname
}
