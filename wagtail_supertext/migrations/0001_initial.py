from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="SupertextState",
            fields=[
                ("key", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("value", models.TextField(blank=True, default="")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name": "Supertext state", "verbose_name_plural": "Supertext state"},
        ),
    ]
