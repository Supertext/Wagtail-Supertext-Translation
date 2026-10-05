# Supertext Translation for Wagtail

Translate Wagtail pages and snippets with **Supertext AI**, right inside [wagtail-localize](https://wagtail-localize.org/), Wagtail's translation editor.

Open a page, choose **Translate this page**, pick the languages, and click **Translate with Supertext** in the translation editor. Every missing string of the page is translated in one request per language; you review, adjust and publish as usual.

- A wagtail-localize machine translator: no new screens for editors to learn
- Whole paragraphs go to Supertext with their bold, italic and link markup, so sentences translate naturally
- Translated page slugs, so translated pages get translated URLs
- Formal or informal tone and custom Supertext language codes per locale
- *Settings → Supertext* in the admin shows the configuration and tests the API key

![The wagtail-localize translation editor with the Translate with Supertext button](docs/images/translation-editor.png)

## Documentation

| Guide | For |
| --- | --- |
| [Installation guide](docs/INSTALLATION.md) | Administrators and developers: requirements, install, API key, locales, settings, troubleshooting |
| [User guide](docs/USER_GUIDE.md) | Editors: translating, reviewing, what gets translated |
| [Developer guide](docs/DEVELOPER.md) | Architecture, API protocol, local development, tests, demo deployment, releases |

Quick start:

```python
# settings.py (wagtail-localize already set up)
INSTALLED_APPS += ["wagtail_supertext"]
WAGTAILLOCALIZE_MACHINE_TRANSLATOR = {
    "CLASS": "wagtail_supertext.SupertextTranslator",
    "OPTIONS": {"API_KEY": os.environ["SUPERTEXT_API_KEY"]},
}
```

## Demo

`demo/` is a Wagtail 8 site with an English sample page and German, French and Italian (Switzerland), deployed to Railway from this repository. See the [developer guide](docs/DEVELOPER.md#demo-railway).

## Changelog and roadmap

See [CHANGELOG.md](CHANGELOG.md) and the [roadmap](docs/DEVELOPER.md#known-limitations--roadmap).

## License

BSD 3-Clause (like Wagtail). © Supertext AG
