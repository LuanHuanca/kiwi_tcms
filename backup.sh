#!/bin/bash
set -e

# Carga automáticamente las variables del .env, sin que tengas que exportarlas manualmente
cd "$(dirname "$0")"
set -a
source .env
set +a

UPLOADS_VOLUME="${UPLOADS_VOLUME:-kiwitcms_uploads}"

FECHA=$(date +%Y%m%d_%H%M%S)
DEST=~/kiwitcms/backups
mkdir -p "$DEST"

echo "[$FECHA] Iniciando backup..."

# 1. Volcado de la base de datos (siempre se hace, no depende de S3)
docker exec -i kiwi_db pg_dump -U kiwi --dbname=kiwi -F c > "$DEST/kiwi_db_$FECHA.bak"
echo "[$FECHA] Dump de base de datos OK: $DEST/kiwi_db_$FECHA.bak"

# 2. Backup del volumen de adjuntos (siempre se hace, no depende de S3)
docker run --rm \
  -v "$UPLOADS_VOLUME":/data:ro \
  -v "$DEST":/backup \
  alpine tar czf /backup/kiwi_uploads_$FECHA.tar.gz -C /data .
echo "[$FECHA] Tar de uploads OK: $DEST/kiwi_uploads_$FECHA.tar.gz"

# 3. Subir a S3 usando el contenedor oficial de AWS CLI (sin instalar nada en el servidor)
# Si todavía no hay credenciales reales, se avisa y se conserva solo el backup local.
PLACEHOLDERS=("" "tu_access_key_id" "tu_secret_access_key" "changeme")
is_placeholder() {
  local v="$1"
  for p in "${PLACEHOLDERS[@]}"; do
    [ "$v" = "$p" ] && return 0
  done
  return 1
}

if is_placeholder "$AWS_ACCESS_KEY_ID" || is_placeholder "$AWS_SECRET_ACCESS_KEY" || is_placeholder "$AWS_BACKUP_BUCKET_NAME"; then
  echo "[$FECHA] AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_BACKUP_BUCKET_NAME sin configurar todavía."
  echo "[$FECHA] Se omite la subida a S3; el backup queda solo en $DEST."
  exit 0
fi

docker run --rm \
  -v "$DEST":/aws \
  -e AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY \
  -e AWS_DEFAULT_REGION="$AWS_S3_REGION_NAME" \
  amazon/aws-cli s3 cp "/aws/kiwi_db_$FECHA.bak" "s3://$AWS_BACKUP_BUCKET_NAME/postgres/"

docker run --rm \
  -v "$DEST":/aws \
  -e AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY \
  -e AWS_DEFAULT_REGION="$AWS_S3_REGION_NAME" \
  amazon/aws-cli s3 cp "/aws/kiwi_uploads_$FECHA.tar.gz" "s3://$AWS_BACKUP_BUCKET_NAME/uploads/"

echo "[$FECHA] Backup completado (local + S3)."