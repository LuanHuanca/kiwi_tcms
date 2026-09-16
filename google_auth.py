import os
from django.conf import settings

INSTALLED_APPS += ["social_django"]

AUTHENTICATION_BACKENDS = [
    "social_core.backends.google.GoogleOAuth2",
    "django.contrib.auth.backends.ModelBackend",
]

SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.environ.get("GOOGLE_OAUTH2_KEY")
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.environ.get("GOOGLE_OAUTH2_SECRET")

# Restringe a cuentas de la empresa
SOCIAL_AUTH_GOOGLE_OAUTH2_WHITELISTED_DOMAINS = ["cirrus-it.net"]

# Habilita el override de templates para el login con Google
settings.TEMPLATES[0]['DIRS'].insert(0, os.path.join(settings.TCMS_ROOT_PATH, 'overridden_templates'))

# Usa nuestro urlconf personalizado, que incluye las rutas de social_django
ROOT_URLCONF = "custom_urls"
