"""Template tags and filters for the sticker collection app."""
from django import template

register = template.Library()

# ── PokeAPI raw GitHub sprite base ───────────────────────────────────────────
_RAW = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon"

# Variant → sprite URL template  (use {dex} as placeholder)
# Chosen to best represent each sticker variant visually:
#   base             → Official high-res artwork (the definitive card image)
#   shiny            → Official shiny artwork (gold/alternative palette)
#   battle_scene     → Black/White animated GIF (dynamic pixel battle energy)
#   chibi            → Pokémon HOME sprite (rounded, 3-D, cute — closest to chibi)
#   manga_panel      → Diamond/Pearl sprite (flat clean pixel lines like manga panels)
#   full_illustration→ Dream World SVG (flat vector art, illustration feel)
#   anime            → HeartGold/SoulSilver sprite (anime-style poses)
_VARIANT_SPRITE: dict[str, str] = {
    "base":              f"{_RAW}/other/official-artwork/{{dex}}.png",
    "shiny":             f"{_RAW}/other/official-artwork/shiny/{{dex}}.png",
    "battle_scene":      f"{_RAW}/versions/generation-v/black-white/animated/{{dex}}.gif",
    "chibi":             f"{_RAW}/other/home/{{dex}}.png",
    "manga_panel":       f"{_RAW}/versions/generation-iv/diamond-pearl/{{dex}}.png",
    "full_illustration": f"{_RAW}/other/dream-world/{{dex}}.svg",
    "anime":             f"{_RAW}/versions/generation-iv/heartgold-soulsilver/{{dex}}.png",
}

# Fallback when no dex number or unknown variant
_FALLBACK = f"{_RAW}/other/official-artwork/{{dex}}.png"


@register.filter
def sticker_sprite(dex_number: int | None, variant: str = "base") -> str:
    """
    Return the PokeAPI sprite URL for a given Pokédex number and sticker variant.

    Usage in templates:
        {{ pokemon.pokedex_number|sticker_sprite:"chibi" }}
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
        {% variant_sprite_url pokemon.pokedex_number "chibi" as url %}
        <img src="{{ url }}">
    """
    return sticker_sprite(dex_number, variant)


@register.filter
def official_artwork(dex_number: int | None) -> str:
    """Shortcut: always returns official artwork URL regardless of variant."""
    if not dex_number:
        return ""
    return f"{_RAW}/other/official-artwork/{dex_number}.png"
