"""wagtail-localize end to end: submit a page for translation, machine-translate it, publish."""

import pytest
from django.contrib.auth import get_user_model
from wagtail.models import Locale, Page
from wagtail_localize.machine_translators import get_machine_translator
from wagtail_localize.models import Translation, TranslationSource
from wagtail_localize.views.edit_translation import apply_machine_translation

from tests.fake import FakeSession
from tests.testapp.models import ArticlePage

pytestmark = pytest.mark.django_db


@pytest.fixture
def fake(monkeypatch):
    session = FakeSession()
    from wagtail_supertext.translator import SupertextTranslator

    original = SupertextTranslator.client

    def client(self):
        c = original(self)
        c.session, c.sleep, c.poll_interval = session, (lambda s: None), 0
        return c

    monkeypatch.setattr(SupertextTranslator, "client", client)
    monkeypatch.delenv("SUPERTEXT_API_KEY", raising=False)
    monkeypatch.delenv("SUPERTEXT_API_ENDPOINT", raising=False)
    return session


@pytest.fixture
def page():
    en = Locale.objects.get_or_create(language_code="en")[0]
    Locale.objects.get_or_create(language_code="de-ch")
    Locale.objects.get_or_create(language_code="fr-ch")
    root = Page.get_first_root_node()
    article = ArticlePage(
        title="Swiss chocolate",
        slug="swiss-chocolate-shipped-worldwide",
        locale=en,
        intro='<p>Made by hand in <b>Bern</b>. <a href="https://www.supertext.com">Read more</a>.</p>',
        body=[("heading", "From Bern to the world"), ("paragraph", "<p>Fresh <i>local</i> ingredients.</p>")],
    )
    root.add_child(instance=article)
    return article


def translate(page, code, user):
    source, _ = TranslationSource.get_or_create_from_instance(page)
    translation = Translation.objects.create(source=source, target_locale=Locale.objects.get(language_code=code))
    translation.save_target(user=user)  # creates the (draft) translated page
    applied = apply_machine_translation(translation.id, user, get_machine_translator())
    translation.save_target(user=user, publish=True)
    return applied, page.get_translation(Locale.objects.get(language_code=code)).specific


def test_translator_is_configured():
    translator = get_machine_translator()
    assert translator.display_name == "Supertext"


def test_translates_a_page(fake, page):
    user = get_user_model().objects.create_superuser("admin", "admin@example.com", "pw")
    applied, german = translate(page, "de-ch", user)

    assert applied
    assert german.title == "[de-CH] Swiss chocolate"
    assert german.slug == "de-ch-swiss-chocolate-shipped-worldwide"  # translated as words, then slugified
    # The link URL and formatting survive; the whole paragraph went to Supertext as one string.
    assert '<a href="https://www.supertext.com">[de-CH] Read more</a>' in german.intro
    assert "<b>[de-CH] Bern</b>" in german.intro
    assert german.body[0].value == "[de-CH] From Bern to the world"
    assert "<i>[de-CH] local</i>" in german.body[1].value.source

    # One document per target language, every string in its own data-st-id element
    post = fake.calls[0]
    assert post["data"]["target_lang"] == "de-CH" and post["data"]["source_lang"] == "en"
    html = post["files"]["file"][1].decode()
    assert '<div data-st-id="0">' in html and 'href' not in html  # wagtail-localize strips attributes first


def test_politeness_from_language_settings(fake, page):
    user = get_user_model().objects.create_superuser("admin", "admin@example.com", "pw")
    translate(page, "fr-ch", user)
    assert fake.calls[0]["data"] == {"target_lang": "fr-CH", "source_lang": "en", "politeness": "more"}


def test_nothing_left_to_translate(fake, page):
    user = get_user_model().objects.create_superuser("admin", "admin@example.com", "pw")
    translate(page, "de-ch", user)
    translation = Translation.objects.get(target_locale__language_code="de-ch")
    assert apply_machine_translation(translation.id, user, get_machine_translator()) is False


def test_errors_become_a_message_in_the_editor(monkeypatch, page, client):
    session = FakeSession(statuses=["limit_exceeded"])
    from wagtail_supertext.translator import SupertextTranslator

    original = SupertextTranslator.client

    def fake_client(self):
        c = original(self)
        c.session, c.sleep, c.poll_interval = session, (lambda s: None), 0
        return c

    monkeypatch.setattr(SupertextTranslator, "client", fake_client)
    user = get_user_model().objects.create_superuser("admin", "admin@example.com", "pw")
    source, _ = TranslationSource.get_or_create_from_instance(page)
    translation = Translation.objects.create(source=source, target_locale=Locale.objects.get(language_code="de-ch"))
    translation.save_target(user=user)
    client.force_login(user)
    response = client.post(f"/admin/localize/translate/{translation.id}/machine_translate/?next=/admin/", follow=True)
    assert response.status_code == 200
    assert any("limit is exceeded" in str(m) for m in response.context["messages"])


def test_status_page(client, monkeypatch):
    monkeypatch.delenv("SUPERTEXT_API_KEY", raising=False)
    user = get_user_model().objects.create_superuser("admin", "admin@example.com", "pw")
    Locale.objects.get_or_create(language_code="fr-ch")
    client.force_login(user)
    response = client.get("/admin/supertext/")
    assert response.status_code == 200
    html = response.content.decode()
    assert "Set (Django settings)" in html and "https://api.supertext.com/v1/" in html and "fr-CH" in html
