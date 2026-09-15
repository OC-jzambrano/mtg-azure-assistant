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

variable "acr_sku" {
  type        = string
  default     = "Basic"
  description = "SKU for Azure Container Registry"
}

variable "container_image" {
  type        = string
  default     = ""
  description = "Full container image path. If empty, defaults to the built ACR image."
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
  sensitive   = true
  description = "Admin password for PostgreSQL Flexible Server"
}

variable "postgres_sku_name" {
  type        = string
  default     = "B_Standard_B1ms"
  description = "SKU for PostgreSQL Flexible Server (Burstable B1ms is cost-effective for dev/test)"
}

# External Existing Azure OpenAI / Foundry Service configuration
variable "azure_openai_endpoint" {
  type        = string
  description = "Endpoint of existing Azure OpenAI / Foundry resource (e.g. https://<name>.openai.azure.com/)"
}

variable "azure_openai_api_key" {
  type        = string
  sensitive   = true
  description = "API key for existing Azure OpenAI / Foundry resource"
}

variable "azure_openai_deployment" {
  type        = string
  default     = "gpt-4.1-mini"
  description = "Deployment name for standard completions / structured output (e.g. gpt-4.1-mini)"
}

variable "azure_openai_reasoning_deployment" {
  type        = string
  default     = "gpt-4o"
  description = "Deployment name for complex reasoning / CoT rules judgments (e.g. gpt-4o)"
}

variable "azure_openai_embedding_deployment" {
  type        = string
  default     = "text-embedding-3-small"
  description = "Deployment name for text embeddings"
}

variable "embedding_dimensions" {
  type        = number
  default     = 1536
  description = "Dimensionality of embedding vectors"
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

variable "langfuse_base_url" {
  type        = string
  default     = "https://cloud.langfuse.com"
  description = "Langfuse project region endpoint. Keys are provisioned separately in Key Vault."
}

variable "langfuse_capture_content" {
  type        = bool
  default     = true
  description = "Capture chat content in Langfuse, matching the application default."
}
