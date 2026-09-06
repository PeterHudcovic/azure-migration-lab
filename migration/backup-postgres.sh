#!/bin/bash
set -e

TIMESTAMP=$(date +%Y%m%d_%H%M%S)

pg_dump \
  -h "$SOURCE_DB_HOST" \
  -U "$SOURCE_DB_USER" \
  -d "$SOURCE_DB_NAME" \
  -Fc \
  -f "migrationdb_${TIMESTAMP}.dump"

echo "Backup completed"