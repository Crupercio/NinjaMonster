"""App config for the pokemon app."""
from django.apps import AppConfig


class PokemonConfig(AppConfig):
    name = "apps.pokemon"
    verbose_name = "Pokemon"

    def ready(self) -> None:
        """Import signals so they are registered when Django starts."""
        import apps.pokemon.signals  # noqa: F401
