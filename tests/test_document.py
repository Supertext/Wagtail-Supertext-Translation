from wagtail_supertext.conf import bcp47, load


def test_language_codes():
    assert bcp47("de-ch") == "de-CH"
    assert bcp47("zh-hans") == "zh-Hans"
    options = load({"LANGUAGES": {"fr": {"code": "fr-CH", "politeness": "more"}}})
    assert options.target_code("fr") == "fr-CH"
    assert options.politeness("fr") == "more"
    assert options.target_code("it-ch") == "it-CH"
    assert options.politeness("it-ch") == "default"


def test_environment_variables_win(monkeypatch):
    monkeypatch.setenv("SUPERTEXT_API_KEY", "Supertext-Auth-Key from-env")
    monkeypatch.setenv("SUPERTEXT_API_ENDPOINT", "http://127.0.0.1:8765/v1/")
    options = load({"API_KEY": "from-settings", "ENVIRONMENT": "staging"})
    assert options.api_key == "from-env" and options.api_key_source == "environment"
    assert options.base_url == "http://127.0.0.1:8765/v1/"


def test_supertext_language_codes():
    options = load({"LANGUAGES": {"de": {"code": "de_ch"}, "nb": {"code": "nb-no"}}})
    # Target: regional code; bare codes get a default region.
    assert options.target_code("fr") == "fr-FR"
    assert options.target_code("en") == "en-US"
    assert options.target_code("fr_ch") == "fr-CH"
    assert options.target_code("pt-br") == "pt-BR"
    assert options.target_code("zh-hant") == "zh-Hant"
    assert options.target_code("es-419") == "es-419"
    assert options.target_code("xx") == "xx"  # unknown: sent unchanged
    # The override wins (normalized).
    assert options.target_code("de") == "de-CH"
    # Source: bare language, from the override if there is one.
    assert options.source_code("en") == "en"
    assert options.source_code("en-gb") == "en"
    assert options.source_code("de") == "de"
    # Same language, other region is a valid pair.
    assert options.target_code("en-gb") != options.target_code("en")
