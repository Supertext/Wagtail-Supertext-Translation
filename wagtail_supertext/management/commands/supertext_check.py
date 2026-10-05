from django.core.management.base import BaseCommand, CommandError

from wagtail_supertext import conf
from wagtail_supertext.client import SupertextError


class Command(BaseCommand):
    help = "Checks the Supertext API key (cost-free GET /features)."

    def handle(self, *args, **options):
        config = conf.load()
        self.stdout.write(f"API: {config.base_url}")
        self.stdout.write(f"API key: {'set (' + config.api_key_source + ')' if config.api_key else 'missing'}")
        try:
            config.client().validate_api_key()
        except SupertextError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS("Connected. The API key works."))
