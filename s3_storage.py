import os

# Valores de relleno que se usan en el .env de ejemplo antes de tener las
# credenciales reales de AWS. Si detectamos cualquiera de estos (o vacío),
# tratamos S3 como "no configurado todavía".
_PLACEHOLDER_VALUES = {"", "tu_access_key_id", "tu_secret_access_key", "changeme"}


def _is_configured(value):
    return bool(value) and value.strip().lower() not in _PLACEHOLDER_VALUES


_AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
_AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
_AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME", "")

S3_CONFIGURED = (
    _is_configured(_AWS_ACCESS_KEY_ID)
    and _is_configured(_AWS_SECRET_ACCESS_KEY)
    and _is_configured(_AWS_STORAGE_BUCKET_NAME)
)

if S3_CONFIGURED:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": _AWS_STORAGE_BUCKET_NAME,
                "region_name": os.environ.get("AWS_S3_REGION_NAME"),
                "access_key": _AWS_ACCESS_KEY_ID,
                "secret_key": _AWS_SECRET_ACCESS_KEY,
                "endpoint_url": os.environ.get("AWS_S3_ENDPOINT_URL") or None,
            },
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
else:
    # Sin credenciales S3 reales todavía: los adjuntos se guardan en el
    # volumen local 'uploads' (ya montado en /Kiwi/uploads y servido por
    # nginx en /uploads/). Cuando se configuren las keys reales, correr
    # migrate_uploads_to_s3.sh para subir lo acumulado y luego reconstruir
    # este contenedor para que empiece a usar S3 automáticamente.
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }