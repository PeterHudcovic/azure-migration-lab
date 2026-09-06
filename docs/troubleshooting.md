# Troubleshooting Runbook

## Pod is not running

Check Pods:

kubectl get pods

Describe the failing Pod:

kubectl describe pod <POD_NAME>

Check logs:

kubectl logs <POD_NAME>

## Application is unavailable

Check Deployment:

kubectl get deployment

Check Service:

kubectl get service

Check endpoints:

kubectl get endpoints

Check application logs:

kubectl logs deployment/migration-app

## Image cannot be pulled

Check Pod events:

kubectl describe pod <POD_NAME>

Verify image exists in ACR (Azure Container Registry):

az acr repository show-tags --name acrmigrationlab --repository migration-app

## Database connection fails

Check PostgreSQL Pod:

kubectl get pod migration-postgresql-0

Check PostgreSQL logs:

kubectl logs migration-postgresql-0

Check Kubernetes Secret:

kubectl get secret migration-postgresql-secret

Test database connectivity from the application and inspect application logs.

## Deployment fails

Check Helm history:

helm history migration-app

Check Kubernetes rollout:

kubectl rollout status deployment/migration-app

If necessary, rollback:

helm rollback migration-app <REVISION>