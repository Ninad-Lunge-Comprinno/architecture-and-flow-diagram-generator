# Azure Shape Catalog (starter set)

Service keys usable in architecture diagrams under `provider: azure`.
Azure uses the `mxgraph.azure.*` stencil family. This is a starter set; extend
it following the workflow at the bottom.

| key | category | fill | stencil | default label |
|-----|----------|------|---------|---------------|
| aks | containers | #0079D6 | mxgraph.azure.azure_kubernetes_service | AKS |
| app_service | compute | #0079D6 | mxgraph.azure.app_services | App Service |
| application_gateway | networking | #0079D6 | mxgraph.azure.application_gateway | Application Gateway |
| blob_storage | storage | #0079D6 | mxgraph.azure.blob_storage | Blob Storage |
| cosmos_db | database | #0079D6 | mxgraph.azure.azure_cosmos_db | Cosmos DB |
| function_app | compute | #0079D6 | mxgraph.azure.function_apps | Function App |
| key_vault | security | #0079D6 | mxgraph.azure.key_vault | Key Vault |
| load_balancer | networking | #0079D6 | mxgraph.azure.load_balancer | Load Balancer |
| sql_database | database | #0079D6 | mxgraph.azure.sql_database | Azure SQL Database |
| virtual_machine | compute | #0079D6 | mxgraph.azure.virtual_machine | Virtual Machine |
| virtual_network | networking | #0079D6 | mxgraph.azure.virtual_networks | Virtual Network |

## Adding a new Azure service

1. Add a row to the table above with: key, category, fill color, stencil, and default label
2. The stencil must be a valid `mxgraph.azure.*` shape
3. Test by placing the icon in a diagram to verify it renders correctly
