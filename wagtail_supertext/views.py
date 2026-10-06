"""Settings → Supertext: shows the configuration and tests the API key."""

from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.translation import gettext as _
from wagtail.models import Locale

from . import conf
from .client import API_KEY_URL, SIGNUP_URL, SupertextError


def status(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    options = conf.load()
    if request.method == "POST":
        try:
            options.client().validate_api_key()
            messages.success(request, _("Connected. The API key works."))
        except SupertextError as error:
            messages.error(request, str(error))
        return redirect("wagtail_supertext_status")

    config = getattr(settings, "WAGTAILLOCALIZE_MACHINE_TRANSLATOR", None) or {}
    locales = []
    default = getattr(settings, "LANGUAGE_CODE", "")
    for locale in Locale.objects.order_by("language_code"):
        locales.append(
            {
                "code": locale.language_code,
                "name": locale.get_display_name(),
                "is_source": locale.language_code.lower() == default.lower(),
                "target": options.target_code(locale.language_code),
                "politeness": options.politeness(locale.language_code),
            }
        )

    return TemplateResponse(
        request,
        "wagtail_supertext/status.html",
        {
            "page_title": _("Supertext"),
            "header_title": _("Supertext"),
            "header_icon": "globe",
            "active": config.get("CLASS") == conf.TRANSLATOR_CLASS,
            "options": options,
            "locales": locales,
            "signup_url": SIGNUP_URL,
            "api_key_url": API_KEY_URL,
        },
    )
