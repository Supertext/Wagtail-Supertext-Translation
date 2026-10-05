from wagtail_supertext import document
from wagtail_supertext.conf import bcp47, load


def test_round_trip_keeps_inline_tags():
    strings = ['Every praline is made in <b>Bern</b>. <a id="a1">Read more</a>.', "Fish &amp; chips", "Grüezi"]
    html = document.build(strings)
    assert '<div data-st-id="0">Every praline' in html
    assert document.parse(html) == {0: strings[0], 1: strings[1], 2: strings[2]}


def test_chunks():
    assert document.chunks(["aaaa", "bbbb", "cc"], 9) == [[0, 1], [2]]
    assert document.chunks(["x" * 20], 9) == [[0]]


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
