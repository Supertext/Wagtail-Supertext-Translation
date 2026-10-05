"""Plugin options: the OPTIONS of WAGTAILLOCALIZE_MACHINE_TRANSLATOR, plus environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .client import SupertextClient, base_url_for, normalize_key

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

    @property
    def base_url(self) -> str:
        return base_url_for(self.environment, self.endpoint)

    def target_code(self, language_code: str) -> str:
        """Supertext target for a Wagtail language code: the LANGUAGES override, else BCP-47 (de-ch -> de-CH)."""
        override = (self.language(language_code).get("code") or "").strip()
        return override or bcp47(language_code)

    def politeness(self, language_code: str) -> str:
        value = self.language(language_code).get("politeness") or "default"
        return value if value in ("more", "less") else "default"

    def language(self, language_code: str) -> dict[str, str]:
        for key in (language_code, language_code.lower(), bcp47(language_code)):
            if key in self.languages:
                return self.languages[key] or {}
        return {}

    def client(self, **kwargs) -> SupertextClient:
        return SupertextClient(
            self.api_key, self.base_url, poll_timeout=self.timeout, poll_interval=self.poll_interval, **kwargs
        )


def bcp47(language_code: str) -> str:
    """de-ch -> de-CH, zh-hans -> zh-Hans, fr -> fr."""
    parts = language_code.replace("_", "-").split("-")
    out = [parts[0].lower()]
    for part in parts[1:]:
        out.append(part.upper() if len(part) == 2 else part.capitalize())
    return "-".join(out)


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
    )
