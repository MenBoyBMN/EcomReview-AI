#!/bin/sh
# Nightly PostgreSQL backup script for EcomReview AI Production Pilot
# Usage (cron): 0 2 * * * /path/to/scripts/backup_pg.sh
set -eu

BACKUP_DIR="${BACKUP_DIR:-./backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
CONTAINER_NAME="${PG_CONTAINER:-ecomreview_db}"
PG_USER="${POSTGRES_USER:-ecom_user}"
PG_DB="${POSTGRES_DB:-ecomreview}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "$BACKUP_DIR"
OUT_FILE="${BACKUP_DIR}/${PG_DB}_${TS}.sql.gz"

echo "[backup_pg] Dumping database '${PG_DB}' from container '${CONTAINER_NAME}'..."
docker exec "$CONTAINER_NAME" pg_dump -U "$PG_USER" -d "$PG_DB" --no-owner --no-acl | gzip > "$OUT_FILE"

echo "[backup_pg] Saved backup: ${OUT_FILE} ($(du -h "$OUT_FILE" | cut -f1))"

if [ -n "${BACKUP_S3_URI:-}" ] && command -v aws >/dev/null 2>&1; then
  echo "[backup_pg] Uploading to ${BACKUP_S3_URI}..."
  if [ -n "${BACKUP_S3_ENDPOINT_URL:-}" ]; then
    # Cloudflare R2 or S3-compatible object storage
    aws s3 cp --endpoint-url "$BACKUP_S3_ENDPOINT_URL" "$OUT_FILE" "${BACKUP_S3_URI%/}/$(basename "$OUT_FILE")"
  else
    aws s3 cp "$OUT_FILE" "${BACKUP_S3_URI%/}/$(basename "$OUT_FILE")"
  fi
fi

find "$BACKUP_DIR" -type f -name "${PG_DB}_*.sql.gz" -mtime +"$RETENTION_DAYS" -delete
echo "[backup_pg] Pruned backups older than ${RETENTION_DAYS} days."

# CreBy: MenBoyBMN
