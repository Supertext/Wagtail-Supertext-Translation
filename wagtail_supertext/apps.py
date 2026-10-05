from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class WagtailSupertextConfig(AppConfig):
    name = "wagtail_supertext"
    label = "wagtail_supertext"
    verbose_name = _("Supertext Translation")
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import errors

        errors.install()
