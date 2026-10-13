from django.db import models


class SupertextState(models.Model):
    """Small key/value store of the plugin: the version reporter's JSON state (``key = "reporter"``).

    Never holds the API key: the key check keeps only a SHA-256 fingerprint of it.
    """

    key = models.CharField(max_length=64, primary_key=True)
    value = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Supertext state"
        verbose_name_plural = "Supertext state"

    def __str__(self):
        return self.key
