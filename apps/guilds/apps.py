"""App config for the guild/clan system."""
from django.apps import AppConfig


class GuildsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.guilds"
    verbose_name = "Guilds"
