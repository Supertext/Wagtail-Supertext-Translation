"""Plugin options: the OPTIONS of WAGTAILLOCALIZE_MACHINE_TRANSLATOR, plus environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from ._vendor.supertext import v1 as sdk
from ._vendor.supertext.v1 import Languages
from .client import SupertextClient, SupertextError, base_url_for, normalize_key

TRANSLATOR_CLASS = "wagtail_supertext.SupertextTranslator"


@dataclass
class Options:
    api_key: str = ""
    api_key_source: str = ""  # "environment", "settings" or ""
    environment: str = "live"
    endpoint: str = ""
    languages: dict[str, dict[str, str]] = field(default_factory=dict)
    timeout: float = 180
    poll_interval: float = 2
    version_reports: bool | None = None  # the VERSION_REPORTS option (None: not set, default on)

    @property
    def base_url(self) -> str:
        return base_url_for(self.environment, self.endpoint)

    @property
    def mapping(self) -> dict[str, str]:
        """Wagtail language code → Supertext code: the ``code`` entries of the LANGUAGES option."""
        return {key: str(value.get("code") or "").strip() for key, value in self.languages.items() if str(value.get("code") or "").strip()}

    @property
    def reports_enabled(self) -> bool:
        """*Send version information to Supertext*: SUPERTEXT_VERSION_REPORTS wins over VERSION_REPORTS (default on)."""
        return sdk.reports_enabled(self.version_reports)

    def target_code(self, language_code: str) -> str:
        """Supertext target for a Wagtail language, without guessing.

        The LANGUAGES → ``code`` mapping wins (sent as it is); else a Wagtail code that is a
        Supertext code apart from case and ``_``/``-`` (``de-ch`` → ``de-CH``, ``es``); else
        :class:`SupertextError` ``unsupported_language`` (nothing is sent). No default regions.
        """
        try:
            return Languages.target(language_code, self.mapping)
        except sdk.SupertextError as error:
            raise SupertextError.from_sdk(error) from error

    def target_code_or_none(self, language_code: str) -> str | None:
        """The target code, or ``None`` for a language that isn't mapped (for *Settings → Supertext*)."""
        try:
            return self.target_code(language_code)
        except SupertextError:
            return None

    def source_code(self, language_code: str) -> str:
        """Supertext source for a Wagtail language: the bare language of the mapping or the code (``en-us`` → ``en``)."""
        mapped = self.mapping_for(language_code)
        try:
            return Languages.source(mapped or language_code)
        except sdk.SupertextError as error:
            raise SupertextError.from_sdk(sdk.SupertextError(error.code, source_lang=language_code)) from error

    def mapping_for(self, language_code: str) -> str:
        return str(self.language(language_code).get("code") or "").strip()

    def politeness(self, language_code: str) -> str:
        value = self.language(language_code).get("politeness") or "default"
        return value if value in ("more", "less") else "default"

    def politeness_supported(self, language_code: str) -> bool | None:
        """Whether Supertext offers formal/informal for the locale's target (``None``: unknown or unmapped)."""
        target = self.target_code_or_none(language_code)
        return Languages.supports_politeness(target) if target else None

    def language(self, language_code: str) -> dict[str, str]:
        wanted = _key(language_code)
        for key, value in self.languages.items():
            if _key(key) == wanted:
                return value or {}
        return {}

    def client(self, **kwargs) -> SupertextClient:
        return SupertextClient(
            self.api_key, self.base_url, poll_timeout=self.timeout, poll_interval=self.poll_interval, **kwargs
        )


def _key(code: str) -> str:
    return code.strip().replace("_", "-").lower()


def bcp47(language_code: str) -> str:
    """de-ch -> de-CH, zh-hans -> zh-Hans, fr -> fr (for display)."""
    parts = language_code.replace("_", "-").split("-")
    out = [parts[0].lower()]
    for part in parts[1:]:
        out.append(part.upper() if len(part) == 2 else part.capitalize())
    return "-".join(out)


def _flag(value) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return value.strip().lower() not in ("0", "false", "off", "no")
    return bool(value)


def load(options: dict | None = None) -> Options:
    """Options from the given dict (or Django settings), with SUPERTEXT_API_KEY / SUPERTEXT_API_ENDPOINT winning."""
    if options is None:
        from django.conf import settings

        config = getattr(settings, "WAGTAILLOCALIZE_MACHINE_TRANSLATOR", None) or {}
        options = config.get("OPTIONS", {}) if config.get("CLASS") == TRANSLATOR_CLASS else {}

    env_key = os.environ.get("SUPERTEXT_API_KEY", "")
    key = env_key or str(options.get("API_KEY") or "")
    return Options(
        api_key=normalize_key(key),
        api_key_source="environment" if env_key else ("settings" if key else ""),
        environment=str(options.get("ENVIRONMENT") or "live"),
        endpoint=os.environ.get("SUPERTEXT_API_ENDPOINT", "") or str(options.get("ENDPOINT") or ""),
        languages={str(k): dict(v or {}) for k, v in (options.get("LANGUAGES") or {}).items()},
        timeout=float(options.get("TIMEOUT") or 180),
        poll_interval=float(options.get("POLL_INTERVAL") or 2),
        version_reports=_flag(options.get("VERSION_REPORTS")),
    )
