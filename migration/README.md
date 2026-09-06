# PostgreSQL Migration

## Migration flow

1. Verify source PostgreSQL database.
2. Create backup using `pg_dump`.
3. Transfer backup to target environment.
4. Restore using `pg_restore`.
5. Validate tables and application connectivity.
6. Stop writes to the source database.
7. Perform final backup and restore.
8. Switch application connection to the target database.
9. Validate application.
10. Keep source database available for rollback.

## Rollback

If validation fails:

1. Switch application connection back to the source database.
2. Verify source database connectivity.
3. Restart application workloads if required.
4. Investigate target database failure.