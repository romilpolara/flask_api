# Azure Deployment Notes

This project is prepared for Azure Container Apps.

The simplest deployment path is:

1. Install Azure CLI.
2. Run `az login`.
3. Execute `scripts/deploy-azure.ps1`.

The deployment script will:

- create a resource group
- create an Azure Container Registry
- build the Docker image in ACR
- create a Container Apps environment
- create or update a public Container App

After deployment, it prints the public API URL.
