# Developer guide — Supertext Translation for Wagtail

How the package is built, how to work on it, and how it is released and deployed.

## Architecture

The package plugs into [wagtail-localize](https://wagtail-localize.org/) as its machine translator. wagtail-localize does the hard parts (splitting pages into strings, the translation editor, keeping translations in sync, publishing); this package only turns strings into translations.

```
Translation editor: "Translate with Supertext"
        │  wagtail_localize.views.edit_translation.machine_translate   (wrapped by errors.py)
        │  apply_machine_translation(): every string of the page without a translation
        ▼
SupertextTranslator.translate(source_locale, target_locale, strings)     translator.py
        │  slugs → words; strings chunked below 900k characters
        │  document.build()   one <div data-st-id="N"> per string
        ▼
SupertextClient.translate_document()     POST file → poll → GET → DELETE   client.py
        │
        ▼
document.parse() → StringValue.from_translated_html() → wagtail-localize stores
StringTranslation rows (tool name "Supertext"), the editor reviews and publishes.
```

| Module | Responsibility |
| --- | --- |
| `translator.py` | `SupertextTranslator(BaseMachineTranslator)`: `display_name = "Supertext"`, `can_translate()` (source and target Supertext codes differ), `translate()` |
| `client.py` | Supertext AI file translation API v1 with `requests`. No Django imports; the session and `sleep` are injectable for tests. |
| `document.py` | Builds/parses the HTML document (BeautifulSoup), chunking |
| `conf.py` | Reads `WAGTAILLOCALIZE_MACHINE_TRANSLATOR["OPTIONS"]` plus `SUPERTEXT_API_KEY` / `SUPERTEXT_API_ENDPOINT`; Wagtail language code → Supertext code (`de-ch` → `de-CH`) and tone |
| `errors.py` | Wraps wagtail-localize's `machine_translate` view (installed in `AppConfig.ready()`): a `SupertextError` becomes an error message in the editor instead of an HTTP 500 |
| `views.py`, `wagtail_hooks.py`, `templates/` | *Settings → Supertext* (superusers): configuration, plugin version (read from `wagtail_supertext.__version__`, linked to the GitHub release when it is X.Y.Z), language table, *Test connection* |
| `management/commands/supertext_check.py` | `python manage.py supertext_check` |
| `locale/{de,fr,it}/` | German, French and Italian admin strings (`django.po` and compiled `django.mo`) |

### Strings and markup

wagtail-localize hands over `StringValue`s: inline HTML fragments, one per paragraph or field value, with attributes stripped and replaced by ids (`<a id="a1">our website</a>`; the `href` stays in wagtail-localize). Each goes to Supertext as one `<div data-st-id>` element. The live API translates each such element as a unit and keeps tags and attributes, so whole sentences are translated and `<b>`, `<i>` and `<a id="a1">` come back in the right places. The result goes through `StringValue.from_translated_html()`, which rejects tags wagtail-localize doesn't allow; such strings are left untranslated and logged.

**Slugs:** wagtail-localize offers the page slug as a string. Strings that look like slugs (lower-case words joined by at least two hyphens, e.g. `swiss-chocolate-shipped-worldwide`) are sent as words and slugified afterwards (`WAGTAIL_ALLOW_UNICODE_SLUGS` respected), so translated pages get translated URLs.

**Nothing is overwritten:** wagtail-localize only passes strings that have no translation yet in the target locale.

## Supertext API protocol

Shared with the WordPress plugin and every other Supertext CMS plugin:

1. `POST {base}translate/ai/file`: multipart with `file` (part `Content-Type` exactly `text/html`, no charset, or the API answers 415), `target_lang` (BCP-47, e.g. `de-CH`), optional `source_lang` (primary subtag only, e.g. `en`, or the pair is rejected), optional `politeness` (`more`/`less`). Returns `{file_id}`.
2. `GET …/{file_id}/status` until `done` (`error`, `limit_exceeded`, `deleted` are terminal).
3. `GET …/{file_id}/translation` returns the translated HTML.
4. `DELETE …/{file_id}` (files also expire after 24 h).

Auth header: `Authorization: Supertext-Auth-Key <key>`. The header name must be `Authorization` (`Authentication` gets 403). Supertext shows the key with the prefix, so the client strips a pasted `Supertext-Auth-Key ` and always sends exactly one. Base URLs: `https://api.supertext.com/v1/` (live), `https://api.staging.supertext.com/v1/`, `https://api.testing.supertext.com/v1/`. `GET features` is a cost-free key check (*Test connection*, `supertext_check`).

**Rate limit:** the API limits requests per second per key (HTTP 429). The client retries a 429 up to 4 times, waiting for `Retry-After` if sent, otherwise 1, 2, 4 and 8 seconds plus jitter.

## Local development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[test]" -r demo/requirements.txt
cd demo
python manage.py migrate
DEMO_ADMIN_EMAIL=you@example.com DEMO_ADMIN_PASSWORD='choose-one-1' python manage.py demo_setup
SUPERTEXT_API_KEY=… DJANGO_DEBUG=1 python manage.py runserver
# admin: http://localhost:8000/admin/   site: http://localhost:8000/en/
```

Without `DATABASE_URL` the demo uses SQLite (`demo/db.sqlite3`). To work without a real key, run the stand-in API (`cd tests/docs && node stand-in.mjs`) and start Django with `SUPERTEXT_API_KEY=anything SUPERTEXT_API_ENDPOINT=http://127.0.0.1:8765/v1/`. It returns real German, French and Italian for the demo's pages and `[de-CH] …`-prefixed text for anything else.

## Tests

```bash
pytest
```

- `tests/test_client.py`: the API protocol, auth header and prefix, 429 retries, errors, clean-up.
- `tests/test_document.py`: HTML packing, chunking, language codes, environment variables.
- `tests/test_translator.py`: wagtail-localize end to end on SQLite: a page with rich text, a link and StreamField blocks is submitted, machine-translated through a fake API session and published; checks markup, link, slug, politeness, "nothing left to translate", errors as editor messages, and the settings page.

CI (`.github/workflows/ci.yml`) on every push and pull request:

- **test**: the suite on Python 3.11 with Wagtail 7.0 and Django 5.2, 3.12 with Wagtail 7.4 and Django 5.2, and 3.13 with Wagtail 8.0 and Django 6.1.
- **demo**: installs the demo, runs migrations and `demo_setup` twice against PostgreSQL, `supertext_check`, then translates the home page and the sample article into German through the stand-in API and checks the title, slug and markup.

## Demo (Railway)

The public demo is a container built from `demo/Dockerfile`: Wagtail 8 with wagtail-localize and this package, English plus German, French and Italian (Switzerland), a home page and a sample article. It runs on Railway in the `supertext-cms-demos` project, service `Wagtail`, region EU West (Amsterdam): <https://wagtail-production-b129.up.railway.app/> (admin: `/admin/`). The database is a `wagtail` database on the project's PostgreSQL service.

**Deploys:** Railway watches `main` of this repository (`railway.json` points it at `demo/Dockerfile`) and rebuilds on every push.

**What's in `demo/`:**

| File | Purpose |
| --- | --- |
| `Dockerfile` | `python:3.13-slim`, the demo's requirements and this package (installed from the repository), `collectstatic` |
| `entrypoint.sh` | Every start: creates the database if missing, `migrate`, `demo_setup`, then gunicorn on `$PORT` |
| `demo/settings.py` | Settings from environment variables; PostgreSQL via `DATABASE_URL` (database name `WAGTAIL_DB_NAME`); WhiteNoise for static files; Supertext with formal tone for all three languages |
| `home/` | `HomePage` and `ArticlePage` (title, rich-text intro, StreamField with headings, paragraphs, quotes), templates with a language switcher, migrations, and the `demo_setup` command |
| `createdb.py` | Creates the demo database on the server from `DATABASE_URL` |
| `.env.example` | The variables below |

**No volume:** Railway's volume limit for the project is reached, and the demo needs none: everything is in PostgreSQL. Images uploaded in the demo's admin disappear with the next deploy.

**Service variables:**

| Variable | |
| --- | --- |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}`; the demo database (`WAGTAIL_DB_NAME`, default `wagtail`) is created on that server if missing |
| `DJANGO_SECRET_KEY` | Random secret |
| `DEMO_ADMIN_EMAIL`, `DEMO_ADMIN_PASSWORD` | Superuser (the e-mail address is also the username) |
| `DEMO_EDITOR_EMAIL`, `DEMO_EDITOR_PASSWORD` | Optional second account for automated tests and screenshots: in Wagtail's **Moderators** group (edit and publish pages), which `demo_setup` also gives wagtail-localize's *Can submit translation* |
| `SUPERTEXT_API_KEY` | Supertext key used by the translator |
| `SUPERTEXT_API_ENDPOINT` | Optional, e.g. the staging API |
| `PORT` | Port gunicorn listens on (Railway sets it) |

Railway also sets `RAILWAY_PUBLIC_DOMAIN`, which the settings use for `WAGTAILADMIN_BASE_URL` and `CSRF_TRUSTED_ORIGINS`.

**Demo accounts:** on every start `demo_setup` creates the `DEMO_ADMIN` and `DEMO_EDITOR` accounts if no account with that e-mail address or username exists. Existing accounts are never changed; change passwords in the admin. Passwords must pass Django's password validators (at least 8 characters, not too common, not only digits, not too similar to the e-mail address). If one doesn't, that account is skipped with a warning naming the variable and the rule; the demo still starts. Wagtail has no first-run "create admin" screen; without `DEMO_ADMIN_*` there is simply no superuser.

**Run it locally:**

```bash
docker build -f demo/Dockerfile -t supertext-wagtail-demo .
docker run --rm -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:pass@host.docker.internal:5432/postgres -e DJANGO_SECRET_KEY=dev \
  -e DEMO_ADMIN_EMAIL=you@example.com -e DEMO_ADMIN_PASSWORD='choose-one-1' \
  -e SUPERTEXT_API_KEY=… supertext-wagtail-demo
```

## Docs screenshots

The images in `docs/images/` are generated by `tests/docs/screenshots.mjs` (Playwright) from a freshly set-up demo whose translator talks to `tests/docs/stand-in.mjs`. The stand-in returns German, French and Italian for the demo's strings (`samples.json`, real Supertext output). Regenerate them whenever a screen they show changes:

```bash
cd tests/docs && npm install && npx playwright install chromium
npm run stand-in &
# a fresh demo database (migrate + demo_setup with DEMO_* set), served with
# SUPERTEXT_API_KEY=anything SUPERTEXT_API_ENDPOINT=http://127.0.0.1:8765/v1/
BASE_URL=http://127.0.0.1:8000 DEMO_ADMIN_EMAIL=… DEMO_ADMIN_PASSWORD=… \
  DEMO_EDITOR_EMAIL=… DEMO_EDITOR_PASSWORD=… npm run screenshots
```

On *Settings → Supertext* the script replaces the stand-in's local address with the live API address before taking the picture.

## Releasing

Releases are published by `.github/workflows/release.yml` when the version is officially bumped; nobody tags or creates releases by hand.

1. Move the *Unreleased* entries in `CHANGELOG.md` under a new `## X.Y.Z — YYYY-MM-DD` section, and keep an empty *Unreleased* above it.
2. Set the same version in:
   - `wagtail_supertext/__init__.py`: `__version__`, the Python package version
3. Push to `main`. The workflow checks that the version files match `CHANGELOG.md`, then tags `vX.Y.Z` and creates the GitHub release with the CHANGELOG section as notes (0.x versions as pre-releases). A push that adds no new version does nothing, and a version that is already released is skipped. After fixing a failed run, start it again with *Run workflow* on the *Release* workflow.

Publishing to PyPI (`python -m build && twine upload dist/*`) is planned.
## Conventions

- Black-compatible formatting, type hints in new code.
- User-visible admin strings via Django's gettext, translated in `wagtail_supertext/locale/{de,fr,it}/LC_MESSAGES/django.po` (English is the source). New or changed strings need all four languages in the same commit; recompile the `.mo` files with polib (see `CLAUDE.md`). `client.py` has no Django imports, so it marks its error messages with a local `gettext_noop` and keeps `template`/`params` on `SupertextError`; `errors.localized()` translates them in the admin. `tests/test_locale.py` checks that every marked string is in each catalog, placeholders match and the `.mo` files are current.
- Keep the three docs in `docs/` current with every change (see `CLAUDE.md`).

## Known limitations / roadmap

- Translation runs inside the editor's request (up to `TIMEOUT` per language); very large pages may need a longer web server timeout. Planned: background translation for whole subtrees.
- Only machine translation through wagtail-localize. Sites using Wagtail's simple translation (`wagtail.contrib.simple_translation`) instead are not supported.
- No bulk "translate this subtree into all languages with Supertext" yet: submit the subtree with wagtail-localize, then click *Translate with Supertext* per page and language.
- Not on PyPI yet.
- Human (professional) translation orders are not supported yet (the WordPress plugin has them).
