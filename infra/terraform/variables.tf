variable "prefix" {
  type        = string
  default     = "mtg-assistant"
  description = "Prefix for all Azure resource names"
}

variable "environment" {
  type        = string
  default     = "prod"
  description = "Target deployment environment (dev, staging, prod)"
}

variable "location" {
  type        = string
  default     = "westeurope"
  description = "Azure region for resource deployment"
}

variable "openai_location" {
  type        = string
  default     = "swedencentral"
  description = "Azure region for Azure OpenAI (where GPT-4o and embeddings are widely available)"
}

variable "container_image" {
  type        = string
  default     = "mcr.microsoft.com/azuredocs/aci-helloworld:latest"
  description = "Container image for the MTG Assistant FastAPI backend"
}

variable "app_port" {
  type        = number
  default     = 8000
  description = "Port exposed by the FastAPI container"
}

variable "postgres_admin_user" {
  type        = string
  default     = "mtgadmin"
  description = "Admin username for PostgreSQL Flexible Server"
}

variable "postgres_admin_password" {
  type        = string
  default     = "P@ssw0rdMTG2026!Secure"
  sensitive   = true
  description = "Admin password for PostgreSQL Flexible Server"
}

variable "postgres_sku_name" {
  type        = string
  default     = "B_Standard_B1ms"
  description = "SKU for PostgreSQL Flexible Server (Burstable B1ms is cost-effective for dev/test)"
}

variable "tags" {
  type = map(string)
  default = {
    Project     = "MTG Call Center AI"
    ManagedBy   = "Terraform"
    Environment = "Production"
  }
  description = "Resource tags"
}
