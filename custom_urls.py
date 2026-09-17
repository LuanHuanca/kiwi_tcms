from django.urls import include, path
from tcms.urls import urlpatterns as _tcms_urlpatterns

urlpatterns = _tcms_urlpatterns + [
    path("", include("social_django.urls", namespace="social")),
]

def add_to_tester_group(backend, user, response, *args, **kwargs):
    from django.contrib.auth.models import Group
    tester_group, _ = Group.objects.get_or_create(name="Tester")
    user.groups.add(tester_group)
