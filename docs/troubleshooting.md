# Troubleshooting Runbook

## Pod is not running

Check Pods:

kubectl get pods -n prod

Describe the failing Pod:

kubectl describe pod <POD_NAME> -n prod

Check logs:

kubectl logs <POD_NAME> -n prod

## Application is unavailable

Check Deployment:

kubectl get deployment -n prod

Check Service:

kubectl get service -n prod

Check endpoints:

kubectl get endpoints -n prod

Check application logs:

kubectl logs deployment/migration-app-prod -n prod

## Image cannot be pulled

Check Pod events:

kubectl describe pod <POD_NAME> -n prod

Verify image exists in ACR (Azure Container Registry):

az acr repository show-tags --name acrmigrationlab --repository migration-app

## Database connection fails

Check PostgreSQL Pod:

kubectl get pod migration-postgresql-0 -n prod

Check PostgreSQL logs:

kubectl logs migration-postgresql-0 -n prod

Check the Key Vault-backed Secret used in production:

kubectl get secret migration-app-keyvault-secret -n prod

Test database connectivity from the application and inspect application logs.

## Deployment fails

Check Helm history:

helm history migration-app-prod -n prod

Check Kubernetes rollout:

kubectl rollout status deployment/migration-app-prod -n prod

If necessary, rollback:

helm rollback migration-app-prod <REVISION> -n prod