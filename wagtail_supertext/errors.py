"""Show Supertext errors in the translation editor instead of a server error page.

wagtail-localize's "Translate with <translator>" view lets exceptions from the machine
translator through (HTTP 500). This wraps that view: a SupertextError becomes a red message
in the translation editor, and the editor stays where they were.
"""

from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from wagtail.admin.utils import get_valid_next_url_from_request

from .client import SupertextError


def localized(error: SupertextError) -> str:
    """The error's message in the current admin language (the API's own detail stays as sent)."""
    template = getattr(error, "template", None)
    if not template:
        return str(error)
    params = getattr(error, "params", None) or {}
    text = _(template) % params if params else _(template)
    if getattr(error, "detail", ""):
        text += f" ({error.detail})"
    return text


def install():
    from wagtail_localize.views import edit_translation

    original = edit_translation.machine_translate
    if getattr(original, "_supertext", False):
        return

    @wraps(original)
    def machine_translate(request, translation_id):
        try:
            return original(request, translation_id)
        except SupertextError as error:
            messages.error(request, _("Supertext could not translate: %(error)s") % {"error": localized(error)})
            return redirect(get_valid_next_url_from_request(request) or reverse("wagtailadmin_home"))

    machine_translate._supertext = True
    edit_translation.machine_translate = machine_translate
