# Despliegue automático

Cada push a `main` ejecuta las pruebas, construye la imagen Docker etiquetada con
el SHA del commit, la publica en ACR y actualiza `mtg-assistant-app`. También se
puede ejecutar manualmente el workflow desde GitHub Actions sobre `main`.
Los pull requests ejecutan únicamente las pruebas.

GitHub se autentica con OIDC mediante la identidad administrada `mtg-github-deploy`
del grupo `mtg-assistant-prod-rg`. La federación acepta únicamente
`repo:OC-jzambrano@199658043/mtg-azure-assistant@1367648244:ref:refs/heads/main` y la audiencia
`api://AzureADTokenExchange`. No se almacena una contraseña de Azure.

Permisos de la identidad:

- `AcrPush` sobre el registro `mtgassistantacr40p02b`.
- `Contributor` sobre la aplicación `mtg-assistant-app`, limitado a ese recurso.

Los secrets de GitHub requeridos son `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`,
`AZURE_SUBSCRIPTION_ID`, `AZURE_ACR_NAME` y `AZURE_RG_NAME`. El workflow falla
explícitamente si falta alguno. La identidad y sus asignaciones se provisionaron
con Azure CLI, fuera del estado de Terraform de la aplicación.

Los despliegues se serializan. Antes de marcar éxito, el workflow comprueba que
la revisión está saludable, que `/health` responde y que el HTML, JavaScript y
CSS públicos coinciden con el commit. Una comprobación fallida marca el workflow
como fallido; no ejecuta una reversión automática.

## Langfuse en producción

La aplicación necesita `LANGFUSE_ENABLED=true`, `LANGFUSE_BASE_URL` y ambas claves
para emitir trazas. `APPLICATIONINSIGHTS_CONNECTION_STRING` configura Azure Monitor
y no activa Langfuse por sí sola.

Las claves están en Key Vault como `langfuse-public-key` y `langfuse-secret-key`.
Container Apps las resuelve con su identidad administrada. Terraform declara las
referencias y las variables del contenedor; los valores se provisionan fuera de
Terraform para evitar incluirlos en su estado.
En un entorno nuevo, crear ambos secretos en Key Vault antes de crear la
Container App; las referencias requieren que los secretos ya existan.

Para configurar o rotar estas claves desde el `.env` local autorizado:

```powershell
rtk proxy python scripts/configure_langfuse_azure.py
```

El script valida las credenciales contra Langfuse, escribe en Key Vault por HTTPS
y actualiza el contenedor. Requiere una sesión Azure CLI con acceso a esos recursos.
Tras cambiar las claves, comprobar una consulta de producción en Langfuse filtrando
por su `session_id` y el entorno `prod`. La región de `langfuse_base_url` en Terraform
debe coincidir con `LANGFUSE_BASE_URL` del proyecto.
