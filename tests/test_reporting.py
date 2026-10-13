"""Commando Center glue: the setting, state storage, when the reporter runs, the ping endpoint."""

import json

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from wagtail.models import Locale

from wagtail_supertext import __version__, conf, reporting
from wagtail_supertext.models import SupertextState

pytestmark = pytest.mark.django_db
CHALLENGE = "abcdefghijklmnop0123"


@pytest.fixture
def admin(client):
    user = get_user_model().objects.create_superuser("admin", "admin@example.com", "pw")
    client.force_login(user)
    return client


def stored():
    return json.loads(SupertextState.objects.get(key="reporter").value)


def test_first_admin_request_reports_installed(admin, center):
    admin.get("/admin/supertext/")
    (report,) = center.reports
    assert report["event"] == "installed"
    assert report["site_url"] == "http://testserver"
    assert report["plugin"] == {"name": "Wagtail-Supertext-Translation", "version": __version__}
    assert report["system"]["name"] == "Wagtail" and report["runtime"]["name"] == "Python"
    assert report["sdk_version"] == "0.2.0"
    assert report["api_key_configured"] is True and report["api_key_check"]["status"] == "ok"
    assert report["callback"] == {"url": "http://testserver/supertext/ping"}
    assert "test-key" not in json.dumps(report)
    state = stored()
    assert state["reportedKeyStatus"] == "ok" and state["keyCheck"]["status"] == "ok"
    assert "test-key" not in SupertextState.objects.get(key="reporter").value

    # Nothing changed: no new report, no new key check.
    requests_before = len(center.requests)
    admin.get("/admin/supertext/")
    assert len(center.requests) == requests_before


def test_upgrade_is_reported(admin, center):
    admin.get("/admin/supertext/")
    state = stored()
    state["reportedVersions"] = "0.0.1|" + state["reportedVersions"].split("|", 1)[1]
    SupertextState.objects.filter(key="reporter").update(value=json.dumps(state))
    admin.get("/admin/supertext/")
    assert [r["event"] for r in center.reports] == ["installed", "upgraded"]


def test_status_page_shows_check_and_setting(admin):
    admin.get("/admin/supertext/")
    html = admin.get("/admin/supertext/").content.decode()
    assert "API key checked: the connection to Supertext works." in html
    assert "Send version information to Supertext" in html and "<strong>On</strong>" in html
    assert "http://testserver/supertext/ping" in html


def test_test_connection_shows_rejected_key_with_links(admin, center, monkeypatch):
    monkeypatch.setenv("SUPERTEXT_API_KEY", "wrong-key")
    response = admin.post("/admin/supertext/", follow=True)
    text = " ".join(str(m) for m in response.context["messages"])
    assert "Supertext rejected the API key" in text
    assert 'href="https://www.supertext.com/en/integrations/api" target="_blank" rel="noopener"' in text
    assert 'href="https://www.supertext.com/person/en/account/signin"' in text
    assert stored()["keyCheck"]["status"] == "invalid"
    assert center.reports[-1]["api_key_check"]["status"] == "invalid"


def test_check_messages_in_the_admin_language():
    from django.utils import translation

    check = reporting.ApiKeyCheck("error", "2026-10-13T08:00:00Z", 418, None, "x")
    with translation.override("de"):
        assert "Supertext hat mit einem Fehler geantwortet (418)" in reporting.check_message(check)
    with translation.override("it"):
        assert reporting.check_message(reporting.ApiKeyCheck("ok", "2026-10-13T08:00:00Z", 200, None, "x")).startswith("Chiave API verificata")


def test_reports_off_sends_nothing_but_still_checks_the_key(admin, center, monkeypatch, client):
    monkeypatch.setenv("SUPERTEXT_VERSION_REPORTS", "0")
    admin.post("/admin/supertext/")
    assert center.reports == []
    assert stored()["keyCheck"]["status"] == "ok"
    html = admin.get("/admin/supertext/").content.decode()
    assert "<strong>Off</strong>" in html and "SUPERTEXT_VERSION_REPORTS environment variable" in html
    assert client.get(f"/supertext/ping?challenge={CHALLENGE}").status_code == 404


def test_version_reports_option(settings, center, admin):
    settings.WAGTAILLOCALIZE_MACHINE_TRANSLATOR = {**settings.WAGTAILLOCALIZE_MACHINE_TRANSLATOR, "OPTIONS": {"API_KEY": "test-key", "VERSION_REPORTS": False}}
    admin.get("/admin/supertext/")
    assert center.reports == []
    assert conf.load().reports_enabled is False


def test_center_failure_never_breaks_and_backs_off(admin, center):
    center.center_status = None  # unreachable
    assert admin.get("/admin/supertext/").status_code == 200
    assert stored()["lastFailureAt"]
    center.center_status = 202
    admin.get("/admin/supertext/")
    assert center.reports == [] or all(r["event"] == "installed" for r in center.reports)
    assert len([r for r in center.requests if r.url.endswith("/report")]) == 1  # no retry within the hour


def test_storage_failure_never_breaks(admin, monkeypatch):
    def broken():
        raise RuntimeError("database down")

    monkeypatch.setattr(reporting, "load_state", broken)
    assert admin.get("/admin/supertext/").status_code == 200
    assert reporting.run("on_request", conf.load()) is None


def test_ping_endpoint(client):
    response = client.get(f"/supertext/ping?challenge={CHALLENGE}")
    assert response.status_code == 200
    assert json.loads(response.content) == {"ok": True, "plugin": "Wagtail-Supertext-Translation", "challenge": CHALLENGE}
    assert response["Content-Type"] == "application/json" and response["Cache-Control"] == "no-store"
    assert client.get("/supertext/ping?challenge=<script>").status_code == 400
    assert client.get("/supertext/ping").status_code == 400
    assert client.post(f"/supertext/ping?challenge={CHALLENGE}").status_code == 405


def test_authentication_failure_in_a_translation_is_reported_once(center):
    options = conf.load()
    reporting.run("on_request", options)
    reporting.run("authentication_failed", options, http_status=403)
    reporting.run("authentication_failed", options, http_status=403)
    assert [r["event"] for r in center.reports] == ["installed", "api_key_check"]
    assert center.reports[-1]["api_key_check"] == {"status": "invalid", "checked_at": stored()["keyCheck"]["checkedAt"], "http_status": 403}


def test_check_command(center):
    call_command("supertext_check")
    assert [r["event"] for r in center.reports] == ["installed", "check"]


def test_check_command_fails_for_a_rejected_key(center, monkeypatch):
    monkeypatch.setenv("SUPERTEXT_API_KEY", "wrong-key")
    with pytest.raises(CommandError, match="invalid"):
        call_command("supertext_check")


def test_site_url_from_wagtail_settings(settings, rf):
    settings.WAGTAILADMIN_BASE_URL = "https://cms.example.ch/"
    assert reporting.site_url() == "https://cms.example.ch"
    assert reporting.callback_url("https://cms.example.ch") == "https://cms.example.ch/supertext/ping"
    settings.WAGTAILADMIN_BASE_URL = ""
    settings.ALLOWED_HOSTS = ["wagtail.example.ch"]
    assert reporting.site_url(rf.get("/", HTTP_HOST="wagtail.example.ch")) == "http://wagtail.example.ch"


def test_status_page_marks_unmapped_languages(admin, settings):
    Locale.objects.get_or_create(language_code="es-es")
    settings.WAGTAILLOCALIZE_MACHINE_TRANSLATOR = {
        **settings.WAGTAILLOCALIZE_MACHINE_TRANSLATOR,
        "OPTIONS": {"API_KEY": "test-key", "LANGUAGES": {"fr-ch": {"politeness": "more"}}},
    }
    html = admin.get("/admin/supertext/").content.decode()
    assert "Not mapped: set code in the LANGUAGES option" in html
