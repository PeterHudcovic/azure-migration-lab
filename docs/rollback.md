# Deployment Rollback

## Helm rollback

Check deployment history:

helm history migration-app-prod -n prod

Rollback to a previous revision:

helm rollback migration-app-prod <REVISION> -n prod

Verify the deployment:

kubectl rollout status deployment/migration-app-prod -n prod

## Kubernetes rollback

Check rollout history:

kubectl rollout history deployment/migration-app-prod -n prod

Rollback the Deployment:

kubectl rollout undo deployment/migration-app-prod -n prod

## Application validation

Check Pods:

kubectl get pods -n prod

Check application logs:

kubectl logs deployment/migration-app-prod -n prod

Check application health endpoint:

/healthz

Check database connectivity:

/readyz (returns HTTP 503 while PostgreSQL is unreachable, 200 once connected)

## PostgreSQL rollback

If database migration validation fails:

1. Stop writes to the target database.
2. Switch the application connection back to the source PostgreSQL database.
3. Restart the application workload if required.
4. Verify the /healthz endpoint.
5. Verify the /readyz endpoint.
