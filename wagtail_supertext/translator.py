"""The wagtail-localize machine translator."""

from __future__ import annotations

import logging
import re

from django.conf import settings
from django.utils.text import slugify
from wagtail_localize.machine_translators.base import BaseMachineTranslator
from wagtail_localize.strings import StringValue

from . import conf, document
from .client import MAX_DOCUMENT_CHARACTERS

logger = logging.getLogger(__name__)

#: Page slugs reach the translator as plain strings like "swiss-chocolate-shipped-worldwide".
#: Lower-case words joined by at least two hyphens are treated as slugs: translated as words,
#: then turned back into a slug, so translated pages get translated URLs.
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+){2,}$")


class SupertextTranslator(BaseMachineTranslator):
    """
    WAGTAILLOCALIZE_MACHINE_TRANSLATOR = {
        "CLASS": "wagtail_supertext.SupertextTranslator",
        "OPTIONS": {"API_KEY": os.environ.get("SUPERTEXT_API_KEY")},
    }

    wagtail-localize calls ``translate()`` with every string of a page that has no
    translation yet (each a paragraph or field value as inline HTML). They go to Supertext
    as one document, one ``<div data-st-id>`` per string.
    """

    display_name = "Supertext"

    def __init__(self, options):
        super().__init__(options)
        self.config = conf.load(options or {})

    def can_translate(self, source_locale, target_locale):
        return self.config.target_code(source_locale.language_code) != self.config.target_code(target_locale.language_code)

    def translate(self, source_locale, target_locale, strings):
        strings = list(strings)
        if not strings:
            return {}

        client = self.client()
        source = conf.bcp47(source_locale.language_code)
        target = self.config.target_code(target_locale.language_code)
        politeness = self.config.politeness(target_locale.language_code)
        is_slug = [bool(SLUG.match(string.data)) for string in strings]
        data = [string.data.replace("-", " ") if slug else string.data for string, slug in zip(strings, is_slug)]
        allow_unicode = getattr(settings, "WAGTAIL_ALLOW_UNICODE_SLUGS", True)
        result = {}

        for group in document.chunks(data, MAX_DOCUMENT_CHARACTERS):
            html = client.translate_document(document.build([data[i] for i in group]), target, source, politeness)
            translated = document.parse(html)
            for position, index in enumerate(group):
                value = translated.get(position)
                if not value:
                    continue
                if is_slug[index]:
                    slug = slugify(StringValue(value).render_text(), allow_unicode=allow_unicode)
                    if slug:
                        result[strings[index]] = StringValue.from_plaintext(slug)
                    continue
                try:
                    result[strings[index]] = StringValue.from_translated_html(value)
                except Exception:  # wagtail-localize rejects tags it doesn't allow
                    logger.warning("Supertext returned HTML wagtail-localize can't use for %r; left untranslated", data[index][:80])

        return result

    def client(self):
        return self.config.client()
