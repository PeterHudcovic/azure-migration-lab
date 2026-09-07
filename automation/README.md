# AKS Scheduled Start/Stop

PowerShell runbooks and RBAC definition backing the scheduled AKS start/stop
described in the main [README](../README.md#scheduled-cost-optimization).

Deployed as:

- Automation Account: `aa-migration-lab` (resource group `rg-migration-lab`,
  region `northeurope` — Free Trial subscriptions are restricted to a fixed
  set of regions for this resource type)
- Identity: system-assigned managed identity on the Automation Account
  (no credentials, passwords, or client secrets)
- RBAC: custom role `AKS Start-Stop Operator` (see
  `aks-start-stop-role.json`), assigned only at the scope of the
  `aks-migration-lab` cluster resource — not the resource group
- Runbooks: `Start-AksCluster.ps1` / `Stop-AksCluster.ps1`, both PowerShell,
  authenticate with `Connect-AzAccount -Identity` and call the AKS
  start/stop control-plane action via `Invoke-AzRestMethod`
- Schedules: daily 07:45 Europe/Prague (start) and 20:00 Europe/Prague
  (stop), each linked to its runbook

Both runbooks are idempotent: starting an already-running cluster or
stopping an already-stopped cluster is treated as a no-op, not a failure.
