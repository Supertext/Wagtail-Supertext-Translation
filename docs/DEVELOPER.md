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
        │  slugs → words
        ▼
SupertextClient.translate_strings()      client.py, on the Supertext SDK:
        │  one <div data-st-id="N"> per string, documents below 900k characters,
        │  POST file → poll → GET → DELETE
        ▼
translated inner HTML per string → StringValue.from_translated_html() → wagtail-localize stores
StringTranslation rows (tool name "Supertext"), the editor reviews and publishes.
```

| Module | Responsibility |
| --- | --- |
| `translator.py` | `SupertextTranslator(BaseMachineTranslator)`: `display_name = "Supertext"`, `can_translate()` (source and target are different languages; an unmapped locale keeps the button so the editor gets the message), `translate()` (refuses politeness for a target without it, runs the reporter after the translation) |
| `client.py` | The plugin's Supertext client on top of the Supertext SDK: sends the SDK's requests with `requests` (`RequestsTransport`), maps SDK error codes to translatable messages (`SupertextError`). No Django imports; the session and `sleep` are injectable for tests. |
| `_vendor/supertext/` | The [Supertext Python SDK](https://github.com/Supertext/Supertext-API-SDK-and-Guide) (`sdk/python`), the package's own copy, made by `scripts/vendor-sdk.sh`; see *Supertext SDK* |
| `_vendor/plugin_health/` | [Supertext Plugin Health](https://github.com/Supertext/Commando-Center-Supertext-Translation/tree/main/plugin-health) (`plugin-health/python`), the package's own copy, made by `scripts/vendor-plugin-health.sh`; see *Supertext Plugin Health* |
| `conf.py` | Reads `WAGTAILLOCALIZE_MACHINE_TRANSLATOR["OPTIONS"]` plus `SUPERTEXT_API_KEY` / `SUPERTEXT_API_ENDPOINT` / `SUPERTEXT_VERSION_REPORTS`; Wagtail language code → Supertext code (the SDK's `Languages`, see *Language codes*) and tone |
| `reporting.py` | Commando Center: version reports, the API key check and the ping answer (Plugin Health's `InstallationReporter`, `ping_response`, with the SDK's `check_api_key()` as the key check), site URL, state storage, the key-check messages |
| `models.py`, `migrations/` | `SupertextState`: one row `reporter` with the reporter's JSON state |
| `urls.py` | Public URLs, included by the site's `urls.py`: `GET /supertext/ping` |
| `errors.py` | Wraps wagtail-localize's `machine_translate` view (installed in `AppConfig.ready()`): a `SupertextError` becomes an error message in the editor instead of an HTTP 500 |
| `views.py`, `wagtail_hooks.py`, `templates/` | *Settings → Supertext* (superusers): configuration, plugin version (read from `wagtail_supertext.__version__`, linked to the GitHub release when it is X.Y.Z), latest API key check, *Test connection*, the version-reports setting and ping URL, language table with *Not mapped* and tone warnings; `views.ping` (public) |
| `management/commands/supertext_check.py` | `python manage.py supertext_check`: key check (`test_connection`) and a `check` report (`report_check`) |
| `locale/{de,fr,it}/` | German, French and Italian admin strings (`django.po` and compiled `django.mo`) |

### Strings and markup

wagtail-localize hands over `StringValue`s: inline HTML fragments, one per paragraph or field value, with attributes stripped and replaced by ids (`<a id="a1">our website</a>`; the `href` stays in wagtail-localize). Each goes to Supertext as one `<div data-st-id>` element. The live API translates each such element as a unit and keeps tags and attributes, so whole sentences are translated and `<b>`, `<i>` and `<a id="a1">` come back in the right places. The result goes through `StringValue.from_translated_html()`, which rejects tags wagtail-localize doesn't allow; such strings are left untranslated and logged.

**Slugs:** wagtail-localize offers the page slug as a string. Strings that look like slugs (lower-case words joined by at least two hyphens, e.g. `swiss-chocolate-shipped-worldwide`) are sent as words and slugified afterwards (`WAGTAIL_ALLOW_UNICODE_SLUGS` respected), so translated pages get translated URLs.

**Nothing is overwritten:** wagtail-localize only passes strings that have no translation yet in the target locale.

## Supertext API protocol

Shared with the WordPress plugin and every other Supertext plugin, and implemented by the Supertext SDK:

1. `POST {base}translate/ai/file`: multipart with `file` (part `Content-Type` exactly `text/html`, no charset, or the API answers 415), `target_lang` (one of Supertext's exact target codes, e.g. `de-CH`, `es`; see *Language codes*), optional `source_lang` (bare language, e.g. `en`, or the pair is rejected), optional `politeness` (`more`/`less`). Returns `{file_id}`.
2. `GET …/{file_id}/status` until `done` (`error`, `limit_exceeded`, `deleted` are terminal).
3. `GET …/{file_id}/translation` returns the translated HTML.
4. `DELETE …/{file_id}`, also after errors (files also expire after 24 h).

Auth header: `Authorization: Supertext-Auth-Key <key>`; a pasted `Supertext-Auth-Key ` prefix is stripped, so exactly one is sent. Base URLs: `https://api.supertext.com/v1/` (live), `https://api.staging.supertext.com/v1/`, `https://api.testing.supertext.com/v1/`. `GET features` is a cost-free key check (*Test connection*, `supertext_check`).

**Rate limit:** the API limits requests per second per key (HTTP 429). A 429 is retried up to 4 times, waiting for `Retry-After` if sent, otherwise 1, 2, 4 and 8 seconds plus jitter (at most 30 s).

### Supertext SDK

`wagtail_supertext/_vendor/supertext` is the package's own copy of the Supertext Python SDK (`supertext-sdk`), the shared client of all Supertext plugins (since SDK 0.3.0 it provides the client and the API key check, `check_api_key()` and `api_key_fingerprint()`; version reports and the ping come from Supertext Plugin Health, below): a private subpackage, so sites install nothing besides this package and an installed `supertext-sdk` can never clash with it. `COMMIT` names the SDK commit, `VERSION` its version (`client.SDK_VERSION`). Never edit it: fix the SDK repository and copy it again:

```bash
scripts/vendor-sdk.sh                  # latest main of the SDK repository
scripts/vendor-sdk.sh <commit-or-branch>
SDK_DIR=/path/to/clone scripts/vendor-sdk.sh   # a local clone as it is
```

The script copies the whole package with its subpackages (`supertext/__init__.py`, `transport.py`, `version.py` and `v1/`); the plugin imports the API from `_vendor.supertext.v1` (SDK 0.2.0+). Then run `pytest` and note the SDK version in `CHANGELOG.md`. This stays so after the SDK is on PyPI.

How the plugin uses it: `SupertextClient.translate_strings()` packs the strings with the SDK's `html_document` and `plan_batches` and translates each document with `Client.translate_html()`. A string Supertext returns nothing for is left untranslated (wagtail-localize keeps it for the editor) instead of failing the whole page. Errors: the SDK's `SupertextError.code` (`authentication_failure`, `invalid_language_pair`, `quota_exceeded`, `timeout`, …) selects a message in `client.MESSAGES`, translated in the admin; the API's own text is shown as detail. The API key never appears in messages.

### Supertext Plugin Health

Version reports to the Supertext Commando Center, the API key check result and the reachability ping come from **Supertext Plugin Health**, a dependency-free library that lives next to the center ([Supertext/Commando-Center-Supertext-Translation](https://github.com/Supertext/Commando-Center-Supertext-Translation) → `plugin-health/python`). It doesn't talk to Supertext itself: `reporting.py` passes it the SDK's key check (`CallableKeyChecker(check=…check_api_key(), fingerprint=api_key_fingerprint)`) and `SDK_VERSION`. `wagtail_supertext/_vendor/plugin_health` is the package's own copy, next to the SDK's (imported as `wagtail_supertext._vendor.plugin_health`, so an installed `supertext-plugin-health` can never clash with it; it uses relative imports, so nothing is rewritten). `COMMIT` and `VERSION` name its revision. Never edit it: fix it in Commando-Center-Supertext-Translation/plugin-health, then copy it again:

```bash
scripts/vendor-plugin-health.sh plugin-health-v0.1.0               # a release tag (default: main)
PLUGIN_HEALTH_DIR=/path/to/clone scripts/vendor-plugin-health.sh   # a local clone of the center's repository as it is
```

The script fails if an absolute `supertext_plugin_health` import is left. Then run `pytest` and note the version in `CHANGELOG.md`. Its state is the same camelCase JSON the SDK 0.1–0.2 reporter stored, so the switch kept every site's history (no new `installed` report).

## Language codes

Supertext accepts exactly the codes its `GET features` lists (the SDK's `Languages`, from the live API, October 2026): bare sources (`en`, `de`); targets in one exact form each, regional for German, English, French, Italian and Portuguese (`de-CH`, `en-US`, `pt-BR`), with a script for Chinese and Serbian (`zh-Hans`, `sr-Latn`), a dialect for Swiss German (`gsw-u-sd-chzh`), bare for the others (`es`, `nl`, `sl`). Anything else is HTTP 404 `INVALID_LANGUAGE_PAIR`; formal/informal for a target without it (`en-US`, `rm`, …) is HTTP 400 `FEATURE_ERROR` (`unsupported_feature`). The SDK sends codes as given. `conf.py` resolves Wagtail codes **without guessing**:

- **Target** (`Options.target_code`): `Languages.target(code, mapping)`. The mapping is the `code` entries of `LANGUAGES` (sent as they are); else a Wagtail code that equals a Supertext code apart from case and `_`/`-` (`de-ch` → `de-CH`, `es`); else `SupertextError` `unsupported_language` with the Wagtail code (`%(language)s` in the message), and nothing is sent. No default regions: `de` must be mapped (to `de-DE`, `de-CH` or `de-AT`). `target_code_or_none` is for *Settings → Supertext* (*Not mapped*).
- **Source** (`Options.source_code`): `Languages.source(code, mapping)` with the same mapping, which sends a mapped code in its source form (`de-CH` → `de`, `en-US` → `en`; one mapping for both directions), else the code's language (`en-us` → `en`), else `unsupported_language`.
- **Tone:** `politeness` is sent only where `Languages.supports_politeness(target)` isn't `False`; where it is, `translate()` raises `unsupported_feature` before any request (the setting isn't dropped silently), and the settings page warns.
- `can_translate()` is false only when source and target are the same language; an unmapped locale keeps the button, so the editor sees why.

`tests/fake.py` and `tests/docs/stand-in.mjs` accept exactly the SDK's target codes (404 `INVALID_LANGUAGE_PAIR` otherwise) and reject politeness where it isn't offered, like the live API.

## Commando Center: version reports, key check, ping

Protocol: [Commando-Center-Supertext-Translation](https://github.com/Supertext/Commando-Center-Supertext-Translation) → `docs/DEVELOPER.md` → *Report protocol*. Supertext Plugin Health's `InstallationReporter`, `reports_enabled()`, `reporter_state()` and `ping_response()` implement it, with the SDK's `check_api_key()` as the key check; `reporting.py` only supplies what Wagtail knows:

- **Setting:** `VERSION_REPORTS` in the translator's `OPTIONS` (default on), `SUPERTEXT_VERSION_REPORTS` (0/1) wins (`Options.reports_enabled` → `reports_enabled()`). Off: no reports, ping 404. `SUPERTEXT_REPORT_URL` sends reports elsewhere (tests, the stand-in).
- **Report fields:** `site_url` = `WAGTAILADMIN_BASE_URL` (absolute), else the request's scheme and host, else the default `Site`'s `root_url`; plugin `Wagtail-Supertext-Translation` with `wagtail_supertext.__version__`; system `Wagtail` with `wagtail.__version__`; runtime Python (Plugin Health's default); `sdk_version` = the bundled SDK's `SDK_VERSION`; `callback.url` = site URL + `reverse("wagtail_supertext_ping")`, left out when the site's `urls.py` doesn't include `wagtail_supertext.urls`. The key check and reports go through `RequestsTransport` (proxies, certificates; reports through a small adapter from Plugin Health's request type).
- **When:** settings live in Django settings, so there is no `settings_saved`. `on_request` runs in a background thread on *Settings → Supertext* (GET) and after every translation (reports `installed`, `upgraded` or `api_key_check`; checks the key only when its fingerprint changed); *Test connection* runs `test_connection` and waits for it; a translation that gets 401/403 runs `authentication_failed`; `supertext_check` runs `test_connection`, then `report_check`. Calls are serialized per process (a lock); nothing here ever raises into a request or a translation (storage errors are caught too, logged at debug level).
- **State:** `SupertextState(key="reporter")`, the reporter's camelCase JSON (`ReporterState.to_json()`, the same the SDK 0.1–0.2 reporter stored), read back with `reporter_state()` (broken → empty). Only a fingerprint of the key.
- **Ping:** `views.ping` (`GET /supertext/ping`, `require_GET`, no login, no session or CSRF): status, headers (`Content-Type: application/json`, `Cache-Control: no-store`) and body exactly as `ping_response()` returns them; `request._cache_update_cache = False` keeps Django's cache middleware from storing it.
- **Messages:** `reporting.check_message()` has the center's key-check texts (en/de/fr/it via the `.po` files), with the account and API key links (new tab) for `invalid` and `missing`.

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

- `tests/test_client.py`: the plugin's client on the SDK through a fake `requests` session: the API protocol, auth header and prefix, 429 retries, errors and their messages, clean-up, many strings in one document. The SDK's own tests and conformance scenarios run in the SDK repository.
- `tests/test_document.py`: language mapping and exact codes, unmapped languages (no guessing), tone support, environment variables, the version-reports setting.
- `tests/test_reporting.py`: one `installed` report from *Settings → Supertext* (fields, `sdk_version`, callback URL, never the key), nothing more when nothing changed, state stored by the SDK 0.1–0.2 reporter kept (no new report), the bundled Plugin Health version, `upgraded`, *Test connection* with a rejected key (message with links), reports off (nothing sent, key still checked, ping 404), the `VERSION_REPORTS` option, an unreachable center (no retry within the hour), storage failures, the ping answers, a 401/403 reported once, `supertext_check`, the site URL. `tests/conftest.py` sends every report and key check to `tests.fake.FakeTransport` (never the live center or API) in the same thread.
- `tests/test_translator.py`: wagtail-localize end to end on SQLite: a page with rich text, a link and StreamField blocks is submitted, machine-translated through a fake API session and published; checks markup, link, slug, politeness, "nothing left to translate", errors as editor messages, the settings page, unmapped locales (nothing sent), politeness for a target without it, and a rejected key reported to the (fake) center.

CI (`.github/workflows/ci.yml`) on every push and pull request:

- **test**: the suite on Python 3.11 with Wagtail 7.0 and Django 5.2, 3.12 with Wagtail 7.4 and Django 5.2, and 3.13 and 3.14 with Wagtail 8.0 and Django 6.1.
- **demo**: installs the demo, runs migrations and `demo_setup` twice against PostgreSQL, `supertext_check`, checks the `installed` and `check` reports the stand-in center received (plugin name, ping URL, no key) and the ping endpoint, then translates the home page and the sample article into German through the stand-in API and checks the title, slug and markup.

`.github/workflows/checks.yml` and `links.yml` lint the workflows and check the links. `.github/workflows/e2e.yml` runs the end-to-end test against the real Supertext API and regenerates the docs screenshots (see *End-to-end tests*).

## End-to-end tests

The tests above use fakes and the stand-in. `.github/workflows/e2e.yml` also tests against the **real Supertext API**, so changes on Supertext's side (language codes, regional variants, markup, rate limits) show up. It runs on every push to `main` that touches the package, the demo or the tests, on pull requests that change the E2E test or workflow, every Monday (06:04 UTC), and by hand (*Actions → E2E → Run workflow*). It builds the demo image once (Docker layer cache in GitHub Actions) and starts it twice on a PostgreSQL service, each with its own new database (`WAGTAIL_DB_NAME`) and demo accounts made up for the run:

1. **Real API** (repository or organization secret `SUPERTEXT_API_KEY`, set by Remy; without it these steps are skipped with a warning). Version reports are off (`SUPERTEXT_VERSION_REPORTS=0`), so CI runs don't appear in the Commando Center.
   - `tests/e2e/features.mjs` asks the live `GET features` (cost-free, no plugin or SDK code) whether every pair the demo translates (`en` → `de-CH`, `fr-CH`, `it-CH`) is offered; a missing pair fails the run. Whether the plugin's own language list matches the API is the SDK's job (its own tests).
   - `tests/e2e/live.mjs` (Playwright, as the `DEMO_EDITOR` account, through Wagtail's admin as in the user guide): *Translate this page* for every English page into all locales, then in each locale's translation editor *Translate with Supertext* and *Publish in …*. Checked: "Successfully translated with Supertext." and no error message; the Supertext step itself publishes nothing (the live revision only changes when the editor publishes); publishing reports no missing translations; in the database every English page has one copy per locale, every field (title, intro, StreamField blocks) is filled and at least 80 % of them changed (a name like "Supertext Wagtail Demo" can stay the same; unchanged fields are printed as `note`), no `data-st-id`/placeholder/`<div>` is left, bold, italics, list items and links (with their `href`) are kept, the article's slug is translated, the text is in the target language (common words of each language counted) and de-CH has no "ß". *Translate with Supertext* again must change nothing (wagtail-localize passes only untranslated strings): no new pages, published revisions unchanged, no error. Each run translates the demo's two pages into three languages once (around 3,000 characters on the key's account).
2. **Stand-in API**: the docs screenshots (see *Docs screenshots*), so the images don't change with each machine translation. If `docs/images/` changed, a second job pushes the branch `automation/docs-screenshots` and opens (or updates) the pull request "Docs: regenerate screenshots" (only on `main`). This needs *Settings → Actions → General → Allow GitHub Actions to create and approve pull requests*.

If a run fails, the artifact `e2e-debug` has a screenshot of every translation editor result, the demo logs and the stand-in log. Locally:

```bash
cd tests/e2e && npm ci && npx playwright install chromium
# a fresh demo (new database) with a real SUPERTEXT_API_KEY and DEMO_EDITOR_* set, e.g. on port 8081
SUPERTEXT_API_KEY=… E2E_SOURCE=en E2E_TARGETS=de-CH,fr-CH,it-CH npm run features
BASE_URL=http://127.0.0.1:8081 DATABASE_URL=postgresql://user:pass@127.0.0.1:5432/wagtail_live \
  EDITOR_EMAIL=… EDITOR_PASSWORD=… npm run live
```

`live.mjs` also passes against the stand-in API (it returns real translations for the demo's strings), which is how to try changes to it without a key.

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
| `SUPERTEXT_VERSION_REPORTS` | Optional; `0` turns version reports off (default on) |
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
cd tests/docs && npm ci && npx playwright install chromium
npm run stand-in &
# a fresh demo database (migrate + demo_setup with DEMO_* set), served with
# SUPERTEXT_API_KEY=anything SUPERTEXT_API_ENDPOINT=http://127.0.0.1:8765/v1/
# SUPERTEXT_REPORT_URL=http://127.0.0.1:8765/report (reports go to the stand-in, never the live center)
# WAGTAILADMIN_BASE_URL=https://wagtail-production-b129.up.railway.app (the ping URL shown is the live demo's)
BASE_URL=http://127.0.0.1:8000 DEMO_ADMIN_EMAIL=… DEMO_ADMIN_PASSWORD=… \
  DEMO_EDITOR_EMAIL=… DEMO_EDITOR_PASSWORD=… npm run screenshots
```

On *Settings → Supertext* the script replaces the stand-in's local address with the live API address and the key check's time with a fixed one before taking the picture, and makes the window as tall as the page (Wagtail scrolls inside `<main>`). The browser's clock is fixed too, so the images only change when the UI does. The E2E workflow (see *End-to-end tests*) runs the script against a fresh demo on every relevant push to `main` and opens a pull request when the images changed. The stand-in also answers `POST /report` (202) and lists the reports on `GET /report`.

## Code quality and security checks

- **Checks** workflow (`.github/workflows/checks.yml`): [actionlint](https://github.com/rhysd/actionlint) and [zizmor](https://docs.zizmor.sh/) lint the workflows on every push and pull request. Dependency review fails a pull request that adds a package with a known vulnerability (moderate or worse). Actions are pinned to commit SHAs; Dependabot keeps the pins up to date. To run the workflow lint locally: `pip install actionlint-py zizmor`, then `actionlint` and `zizmor .github/workflows` in the repo root.
- **Links** workflow (`.github/workflows/links.yml`): [lychee](https://lychee.cli.rs/) checks the links in all Markdown files weekly and whenever docs change on `main`. Broken links open (or update) the issue "Broken links in the docs". Links that can't work from CI (local URLs, placeholders, pages behind a login) are excluded in `.lycheeignore`.
- Python and the demo's JavaScript are analysed by CodeQL (see below), so this repo runs no separate static analyser.
- GitHub settings (set by Remy's setup script, not stored in the repo): **secret scanning with push protection** (a push containing a known token format is rejected; findings under *Security → Secret scanning*) and **CodeQL default setup** (findings under *Security → Code scanning* and as comments on pull requests; PHP isn't covered by CodeQL, which is why the PHP plugins run PHPStan).

Before starting work in this repo, look at its open findings: code scanning alerts, secret scanning alerts, Dependabot PRs and the "Broken links in the docs" issue.

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
- Model changes need a migration in `wagtail_supertext/migrations` committed with the change (`python -m django makemigrations wagtail_supertext --settings=tests.settings`).
- Keep the three docs in `docs/` current with every change (see `CLAUDE.md`).

## Known limitations / roadmap

- Translation runs inside the editor's request (up to `TIMEOUT` per language); very large pages may need a longer web server timeout. Planned: background translation for whole subtrees.
- Only machine translation through wagtail-localize. Sites using Wagtail's simple translation (`wagtail.contrib.simple_translation`) instead are not supported.
- No bulk "translate this subtree into all languages with Supertext" yet: submit the subtree with wagtail-localize, then click *Translate with Supertext* per page and language.
- Not on PyPI yet.
- Human (professional) translation orders are not supported yet (the WordPress plugin has them).
