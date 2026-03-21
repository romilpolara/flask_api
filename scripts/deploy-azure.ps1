param(
    [string]$SubscriptionId = "",
    [string]$ResourceGroup = "rg-object-detection-api",
    [string]$Location = "centralindia",
    [string]$ContainerRegistry = "acrobjectdetectapi",
    [string]$ContainerAppEnvironment = "env-object-detection-api",
    [string]$ContainerAppName = "ca-object-detection-api",
    [string]$ImageName = "object-detection-api",
    [string]$ImageTag = "latest",
    [string]$Cpu = "2.0",
    [string]$Memory = "4Gi",
    [switch]$SkipAcrBuild
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Test-AzureLogin {
    az account show --output none 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI login not found. Run 'az login' first."
    }
}

function Test-ResourceExists {
    param(
        [string]$Type,
        [string]$Name,
        [string[]]$Args
    )

    & az @Args show --name $Name --output none 2>$null
    return $LASTEXITCODE -eq 0
}

Write-Step "Checking Azure CLI login"
Test-AzureLogin

if ($SubscriptionId) {
    Write-Step "Setting subscription $SubscriptionId"
    az account set --subscription $SubscriptionId
}

Write-Step "Creating resource group $ResourceGroup in $Location"
az group create `
    --name $ResourceGroup `
    --location $Location `
    --output table

Write-Step "Ensuring Azure Container Registry $ContainerRegistry exists"
$acrExists = az acr show --resource-group $ResourceGroup --name $ContainerRegistry --output none 2>$null
if ($LASTEXITCODE -ne 0) {
    az acr create `
        --resource-group $ResourceGroup `
        --name $ContainerRegistry `
        --sku Basic `
        --admin-enabled true `
        --output table
}

$acrServer = az acr show `
    --resource-group $ResourceGroup `
    --name $ContainerRegistry `
    --query loginServer `
    --output tsv

$acrUser = az acr credential show `
    --resource-group $ResourceGroup `
    --name $ContainerRegistry `
    --query username `
    --output tsv

$acrPassword = az acr credential show `
    --resource-group $ResourceGroup `
    --name $ContainerRegistry `
    --query "passwords[0].value" `
    --output tsv

if (-not $SkipAcrBuild) {
    Write-Step "Building Docker image in ACR"
    az acr build `
        --registry $ContainerRegistry `
        --image "${ImageName}:${ImageTag}" `
        .
}

$fullImage = "$acrServer/${ImageName}:${ImageTag}"

Write-Step "Ensuring Container Apps environment $ContainerAppEnvironment exists"
az containerapp env show `
    --resource-group $ResourceGroup `
    --name $ContainerAppEnvironment `
    --output none 2>$null

if ($LASTEXITCODE -ne 0) {
    az containerapp env create `
        --resource-group $ResourceGroup `
        --name $ContainerAppEnvironment `
        --location $Location `
        --output table
}

Write-Step "Creating or updating Container App $ContainerAppName"
az containerapp show `
    --resource-group $ResourceGroup `
    --name $ContainerAppName `
    --output none 2>$null

if ($LASTEXITCODE -eq 0) {
    az containerapp update `
        --resource-group $ResourceGroup `
        --name $ContainerAppName `
        --image $fullImage `
        --set-env-vars PORT=8000 YOLO_CONFIG_DIR=/app/.ultralytics `
        --cpu $Cpu `
        --memory $Memory `
        --output table
} else {
    az containerapp create `
        --resource-group $ResourceGroup `
        --name $ContainerAppName `
        --environment $ContainerAppEnvironment `
        --image $fullImage `
        --target-port 8000 `
        --ingress external `
        --registry-server $acrServer `
        --registry-username $acrUser `
        --registry-password $acrPassword `
        --env-vars PORT=8000 YOLO_CONFIG_DIR=/app/.ultralytics `
        --cpu $Cpu `
        --memory $Memory `
        --min-replicas 1 `
        --max-replicas 1 `
        --output table
}

$appUrl = az containerapp show `
    --resource-group $ResourceGroup `
    --name $ContainerAppName `
    --query properties.configuration.ingress.fqdn `
    --output tsv

Write-Step "Deployment completed"
Write-Host "Public URL: https://$appUrl" -ForegroundColor Green
Write-Host "Swagger docs: https://$appUrl/docs" -ForegroundColor Green
Write-Host "Health check: https://$appUrl/health" -ForegroundColor Green
