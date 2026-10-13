import pytest

from wagtail_supertext.client import SupertextError
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


def test_supertext_language_codes_without_guessing():
    options = load({"LANGUAGES": {"de": {"code": "de-CH"}, "zh-cn": {"code": "zh-Hans"}, "no": {"code": "nb"}}})
    # A Wagtail code that is a Supertext code (case, _/-) is used as it is.
    assert options.target_code("fr_ch") == "fr-CH"
    assert options.target_code("pt-br") == "pt-BR"
    assert options.target_code("zh-hant") == "zh-Hant"
    assert options.target_code("es") == "es"  # bare: Supertext wants it so
    assert options.target_code("en-gb") == "en-GB"
    # The mapping wins and is sent as it is.
    assert options.target_code("de") == "de-CH"
    assert options.target_code("zh-CN") == "zh-Hans"
    assert options.target_code("no") == "nb"
    # Source: bare language, from the mapping if there is one.
    assert options.source_code("en") == "en"
    assert options.source_code("en-gb") == "en"
    assert options.source_code("de") == "de"
    assert options.source_code("zh-cn") == "zh"


@pytest.mark.parametrize("code", ["fr", "en", "es-ES", "sl-SI", "zh-CN", "de_DE_formal", "xx"])
def test_unmapped_languages_are_not_guessed(code):
    options = load({})
    with pytest.raises(SupertextError) as info:
        options.target_code(code)
    assert info.value.code == "unsupported_language"
    assert info.value.params == {"language": code}
    assert options.target_code_or_none(code) is None


def test_unknown_source_language():
    with pytest.raises(SupertextError) as info:
        load({}).source_code("xx")
    assert info.value.code == "unsupported_language" and info.value.params == {"language": "xx"}


def test_politeness_support():
    options = load({"LANGUAGES": {"en-us": {"politeness": "more"}, "de-ch": {"politeness": "more"}}})
    assert options.politeness_supported("de-ch") is True
    assert options.politeness_supported("en-us") is False
    assert options.politeness_supported("de") is None  # not mapped


def test_version_reports_setting(monkeypatch):
    monkeypatch.delenv("SUPERTEXT_VERSION_REPORTS", raising=False)
    assert load({}).reports_enabled is True
    assert load({"VERSION_REPORTS": False}).reports_enabled is False
    monkeypatch.setenv("SUPERTEXT_VERSION_REPORTS", "0")
    assert load({"VERSION_REPORTS": True}).reports_enabled is False
    monkeypatch.setenv("SUPERTEXT_VERSION_REPORTS", "1")
    assert load({"VERSION_REPORTS": False}).reports_enabled is True
