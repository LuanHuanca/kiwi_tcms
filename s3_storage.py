import os

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": os.environ.get("AWS_STORAGE_BUCKET_NAME"),
            "region_name": os.environ.get("AWS_S3_REGION_NAME"),
            "access_key": os.environ.get("AWS_ACCESS_KEY_ID"),
            "secret_key": os.environ.get("AWS_SECRET_ACCESS_KEY"),
            "endpoint_url": os.environ.get("AWS_S3_ENDPOINT_URL") or None,
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}