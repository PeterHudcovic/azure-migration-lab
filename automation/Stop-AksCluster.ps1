# Stops the aks-migration-lab AKS cluster in rg-migration-lab.
# Authenticates using the Automation Account's System-Assigned Managed Identity.
# No credentials, passwords or client secrets are used or stored.

$subscriptionId    = "8b38e1d5-139f-4006-8f2b-ffb32a6ac114"
$resourceGroupName = "rg-migration-lab"
$clusterName       = "aks-migration-lab"

Connect-AzAccount -Identity | Out-Null
Set-AzContext -SubscriptionId $subscriptionId | Out-Null

$path = "/subscriptions/$subscriptionId/resourceGroups/$resourceGroupName/providers/Microsoft.ContainerService/managedClusters/$clusterName/stop?api-version=2024-10-01"

Write-Output "Stopping AKS cluster '$clusterName' in resource group '$resourceGroupName'..."
$response = Invoke-AzRestMethod -Path $path -Method POST

if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
    Write-Output "Stop request accepted (HTTP $($response.StatusCode))."
} elseif ($response.StatusCode -eq 400 -and $response.Content -match "not currently running") {
    Write-Output "Cluster is already stopped. No action needed (HTTP 400, idempotent no-op)."
} else {
    throw "Stop request failed with HTTP $($response.StatusCode): $($response.Content)"
}
