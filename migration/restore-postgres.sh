#!/bin/bash
set -e

pg_restore \
  -h "$TARGET_DB_HOST" \
  -U "$TARGET_DB_USER" \
  -d "$TARGET_DB_NAME" \
  --clean \
  --if-exists \
  "$1"

echo "Restore completed"