#!/bin/bash
set -e

# Sincroniza lo que se guardó localmente (mientras no había keys de S3 reales)
# hacia el bucket de S3, respetando la misma estructura de rutas relativas
# que usa django-storages. Correr UNA VEZ después de poner las keys reales
# en el .env, y ANTES de reconstruir 'web' (o justo después, no importa el
# orden ya que los nombres de archivo/ruta no cambian entre backends).
#
# Uso: ./migrate_uploads_to_s3.sh

cd "$(dirname "$0")"
set -a
source .env
set +a

UPLOADS_VOLUME="${UPLOADS_VOLUME:-kiwitcms_uploads}"

PLACEHOLDERS=("" "tu_access_key_id" "tu_secret_access_key" "changeme")
is_placeholder() {
  local v="$1"
  for p in "${PLACEHOLDERS[@]}"; do
    [ "$v" = "$p" ] && return 0
  done
  return 1
}

if is_placeholder "$AWS_ACCESS_KEY_ID" || is_placeholder "$AWS_SECRET_ACCESS_KEY" || is_placeholder "$AWS_STORAGE_BUCKET_NAME"; then
  echo "AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_STORAGE_BUCKET_NAME todavía no tienen valores reales en .env."
  echo "Configúralos primero; no se migró nada."
  exit 1
fi

# django-attachments guarda cada archivo en:
#   attachments/{app}_{model}/{pk}/{filename}
# La ruta depende del caso/bug/plan y del nombre de archivo, NO de cuándo se
# subió. Si la misma imagen se subió antes a S3, se borraron las keys, y se
# volvió a subir la MISMA imagen al MISMO caso mientras se guardaba local,
# este sync SOBRESCRIBE el objeto existente en S3 con la copia local (no
# crea un duplicado, pero sí reemplaza el original). Por eso el paso previo
# es obligatorio: revisa la lista antes de confirmar.

echo "Vista previa (dry-run) de lo que se subiría/sobrescribiría en s3://$AWS_STORAGE_BUCKET_NAME/ :"
echo "----------------------------------------------------------------------"
docker run --rm \
  -v "$UPLOADS_VOLUME":/data:ro \
  -e AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY \
  -e AWS_DEFAULT_REGION="$AWS_S3_REGION_NAME" \
  amazon/aws-cli s3 sync /data "s3://$AWS_STORAGE_BUCKET_NAME/" --dryrun
echo "----------------------------------------------------------------------"
echo "Las líneas '(dryrun) upload' hacia una ruta que YA EXISTE en el bucket son sobrescrituras, no archivos nuevos."
echo ""
read -p "¿Confirmas subir esto de verdad? (escribe 'si' para continuar): " CONFIRMA
if [ "$CONFIRMA" != "si" ]; then
  echo "Cancelado. No se subió nada."
  exit 0
fi

echo "Sincronizando volumen '$UPLOADS_VOLUME' -> s3://$AWS_STORAGE_BUCKET_NAME/ ..."

docker run --rm \
  -v "$UPLOADS_VOLUME":/data:ro \
  -e AWS_ACCESS_KEY_ID \
  -e AWS_SECRET_ACCESS_KEY \
  -e AWS_DEFAULT_REGION="$AWS_S3_REGION_NAME" \
  amazon/aws-cli s3 sync /data "s3://$AWS_STORAGE_BUCKET_NAME/" --no-progress

echo "Migración completada."
echo "Ahora reconstruye 'web' (docker compose up -d --build) para que Kiwi empiece a leer/escribir en S3."
