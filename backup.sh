#!/bin/bash
set -e

# Carga automáticamente las variables del .env, sin que tengas que exportarlas manualmente
cd "$(dirname "$0")"
set -a
source .env
set +a

FECHA=$(date +%Y%m%d_%H%M%S)
DEST=~/kiwitcms/backups
mkdir -p "$DEST"

echo "[$FECHA] Iniciando backup..."

# 1. Volcado de la base de datos
docker exec -i kiwi_db pg_dump -U kiwi --dbname=kiwi -F c > "$DEST/kiwi_db_$FECHA.bak"

# 2. Backup del volumen de adjuntos
docker run --rm \
  -v kiwitcms_uploads:/data \
  -v "$DEST":/backup \
  alpine tar czf /backup/kiwi_uploads_$FECHA.tar.gz -C /data .

# 3. Subir a S3 usando el contenedor oficial de AWS CLI (sin instalar nada en el servidor)
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

echo "[$FECHA] Backup completado."