"""Public URLs of the plugin (no login): the Commando Center's ping endpoint.

    urlpatterns = [
        path("supertext/", include("wagtail_supertext.urls")),   # before wagtail_urls
        ...
    ]
"""

from django.urls import path

from . import views

urlpatterns = [path("ping", views.ping, name="wagtail_supertext_ping")]
