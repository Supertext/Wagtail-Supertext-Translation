SECRET_KEY = "tests"
DEBUG = False
USE_TZ = True
ROOT_URLCONF = "tests.urls"
LANGUAGE_CODE = "en"
USE_I18N = True
WAGTAIL_I18N_ENABLED = True
LANGUAGES = WAGTAIL_CONTENT_LANGUAGES = [("en", "English"), ("de-ch", "Deutsch (Schweiz)"), ("fr-ch", "Français (Suisse)")]
WAGTAIL_SITE_NAME = "Tests"
WAGTAILADMIN_BASE_URL = "http://testserver"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
INSTALLED_APPS = [
    "wagtail_supertext",
    "tests.testapp",
    "wagtail_localize",
    "wagtail_localize.locales",
    "wagtail.contrib.settings",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.admin",
    "wagtail",
    "modelcluster",
    "taggit",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
STATIC_URL = "/static/"
WAGTAILLOCALIZE_MACHINE_TRANSLATOR = {
    "CLASS": "wagtail_supertext.SupertextTranslator",
    "OPTIONS": {"API_KEY": "Supertext-Auth-Key test-key", "LANGUAGES": {"fr-ch": {"politeness": "more"}}},
}
