from django.core.management.base import BaseCommand, CommandError

from wagtail_supertext import conf, reporting


class Command(BaseCommand):
    help = "Checks the Supertext API key (cost-free GET /features) and sends a version report (if on)."

    def handle(self, *args, **options):
        config = conf.load()
        self.stdout.write(f"API: {config.base_url}")
        self.stdout.write(f"API key: {'set (' + config.api_key_source + ')' if config.api_key else 'missing'}")
        self.stdout.write(f"Send version information to Supertext: {'on' if config.reports_enabled else 'off'}")

        result = reporting.run("test_connection", config)
        check = result.check if result else None
        if config.reports_enabled:
            sent = reporting.run("report_check", config)
            self.stdout.write(f"Version report: {'sent' if sent and sent.sent else 'not sent'}")
        if check is None:
            raise CommandError("The API key couldn't be checked (no site URL: set WAGTAILADMIN_BASE_URL).")
        message = f"API key check: {check.status}" + (f" (HTTP {check.http_status})" if check.http_status else "")
        if check.status != "ok":
            raise CommandError(message)
        self.stdout.write(self.style.SUCCESS(f"{message}. Connected. The API key works."))
