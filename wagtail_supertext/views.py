"""Settings → Supertext: shows the configuration and tests the API key."""

from __future__ import annotations

import os
import re

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET
from wagtail.models import Locale

from . import __version__, conf, reporting
from .client import API_KEY_URL, SIGNUP_URL

RELEASES_URL = "https://github.com/Supertext/Wagtail-Supertext-Translation/releases/tag/v{version}"


def release_url(version: str) -> str | None:
    """Link to the GitHub release when the version looks like one (X.Y.Z)."""
    if re.fullmatch(r"\d+\.\d+\.\d+", version or ""):
        return RELEASES_URL.format(version=version)
    return None


def status(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    options = conf.load()
    if request.method == "POST":
        # Test connection: the SDK's key check (cost-free GET features), stored and reported if it changed.
        result = reporting.run("test_connection", options, request)
        check = result.check if result else None
        text = reporting.check_message(check) or _("The API key couldn't be checked because Supertext can't be reached. The settings are saved; check again later.")
        (messages.success if check and check.status == "ok" else messages.error)(request, text)
        return redirect("wagtail_supertext_status")

    reporting.in_background("on_request", options, request)

    config = getattr(settings, "WAGTAILLOCALIZE_MACHINE_TRANSLATOR", None) or {}
    locales = []
    default = getattr(settings, "LANGUAGE_CODE", "")
    for locale in Locale.objects.order_by("language_code"):
        locales.append(
            {
                "code": locale.language_code,
                "name": locale.get_display_name(),
                "is_source": locale.language_code.lower() == default.lower(),
                "target": options.target_code_or_none(locale.language_code),
                "politeness": options.politeness(locale.language_code),
                "politeness_supported": options.politeness_supported(locale.language_code),
            }
        )

    check = reporting.last_check()
    env_reports = os.environ.get("SUPERTEXT_VERSION_REPORTS", "").strip()
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
            "check": check,
            "check_message": reporting.check_message(check),
            "check_time": reporting.checked_at(check),
            "check_links": bool(check and check.status in ("invalid", "missing")),
            "reports_enabled": options.reports_enabled,
            "reports_source": "environment" if env_reports else ("settings" if options.version_reports is not None else ""),
            "ping_url": reporting.callback_url(reporting.site_url(request) or ""),
            "version": __version__,
            "version_url": release_url(__version__),
        },
    )


@require_GET
def ping(request):
    """Public ping endpoint for the Supertext Commando Center (no login, no session, never cached).

    Answers exactly what the SDK's ``ping_response`` returns: 200 with the challenge echoed,
    400 for a bad challenge, 404 while version reports are off.
    """
    status, headers, body = reporting.ping(request.GET.get("challenge"))
    response = HttpResponse(body, status=status)
    for name, value in headers.items():
        response[name] = value
    request._cache_update_cache = False  # never stored by Django's cache middleware
    return response
