from django.urls import include, path
from tcms.urls import urlpatterns as _tcms_urlpatterns

urlpatterns = _tcms_urlpatterns + [
    path("", include("social_django.urls", namespace="social")),
]
