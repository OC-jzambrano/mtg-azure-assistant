# Despliegue automático

Cada push a `main` ejecuta las pruebas, construye la imagen Docker etiquetada con
el SHA del commit, la publica en ACR y actualiza `mtg-assistant-app`. También se
puede ejecutar manualmente el workflow desde GitHub Actions sobre `main`.
Los pull requests ejecutan únicamente las pruebas.

GitHub se autentica con OIDC mediante la identidad administrada `mtg-github-deploy`
del grupo `mtg-assistant-prod-rg`. La federación acepta únicamente
`repo:OC-jzambrano/mtg-azure-assistant:ref:refs/heads/main` y la audiencia
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
