"""Template tags and filters for the sticker collection app."""
from django import template
from django.conf import settings

register = template.Library()

# Local static sprites root — populated by `manage.py download_sprites`
_STATIC = getattr(settings, "STATIC_URL", "/static/")
_SPRITE_ROOT = f"{_STATIC}sprites"

# PokeAPI fallback base URL (for templates that reference it directly)
_RAW = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon"

# Variant → local static path template  (use {dex} as placeholder)
# Downloaded as-is: base, shiny, battle_scene (gif), anime.
# Effect-generated: all others (created by `manage.py download_sprites`).
_VARIANT_SPRITE: dict[str, str] = {
    "base":         f"{_SPRITE_ROOT}/base/{{dex}}.png",
    "shiny":        f"{_SPRITE_ROOT}/shiny/{{dex}}.png",
    "battle_scene": f"{_SPRITE_ROOT}/battle_scene/{{dex}}.gif",
    "anime":        f"{_SPRITE_ROOT}/anime/{{dex}}.png",
    "watercolor":   f"{_SPRITE_ROOT}/watercolor/{{dex}}.png",
    "sketch":       f"{_SPRITE_ROOT}/sketch/{{dex}}.png",
    "neon_glow":    f"{_SPRITE_ROOT}/neon_glow/{{dex}}.png",
    "burn_scroll":  f"{_SPRITE_ROOT}/burn_scroll/{{dex}}.png",
    "tv_90s":       f"{_SPRITE_ROOT}/tv_90s/{{dex}}.png",
    "holographic":  f"{_SPRITE_ROOT}/holographic/{{dex}}.png",
    "color_swap":   f"{_SPRITE_ROOT}/color_swap/{{dex}}.png",
    "glitter":      f"{_SPRITE_ROOT}/glitter/{{dex}}.png",
    "chrome":       f"{_SPRITE_ROOT}/chrome/{{dex}}.png",
    "cartoon":      f"{_SPRITE_ROOT}/cartoon/{{dex}}.png",
}

_FALLBACK = f"{_SPRITE_ROOT}/base/{{dex}}.png"


@register.filter
def sticker_sprite(dex_number: int | None, variant: str = "base") -> str:
    """
    Return the local static sprite URL for a given Pokédex number and sticker variant.

    Usage in templates:
        {{ pokemon.pokedex_number|sticker_sprite:"watercolor" }}
        {{ sticker.pokemon.pokedex_number|sticker_sprite:sticker.variant }}
    """
    if not dex_number:
        return ""
    template_url = _VARIANT_SPRITE.get(variant, _FALLBACK)
    return template_url.format(dex=dex_number)


@register.simple_tag
def variant_sprite_url(dex_number: int | None, variant: str = "base") -> str:
    """
    Same as sticker_sprite but as a simple_tag for use with {% with %} blocks.

    Usage:
        {% variant_sprite_url pokemon.pokedex_number "watercolor" as url %}
        <img src="{{ url }}">
    """
    return sticker_sprite(dex_number, variant)


@register.filter
def official_artwork(dex_number: int | None) -> str:
    """Shortcut: always returns official artwork URL regardless of variant."""
    if not dex_number:
        return ""
    return f"{_SPRITE_ROOT}/base/{dex_number}.png"
