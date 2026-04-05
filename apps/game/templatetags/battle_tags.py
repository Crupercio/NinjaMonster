"""Custom template tags for the battle UI."""
from django import template

register = template.Library()


@register.filter
def hp_color(hp_percentage: float) -> str:
    """Return a CSS color class based on HP percentage."""
    if hp_percentage > 50:
        return "hp-green"
    if hp_percentage > 20:
        return "hp-yellow"
    return "hp-red"


@register.filter
def status_badge_class(status_name: str) -> str:
    """Return a CSS badge class for a given status name."""
    danger = {"burned", "poisoned", "badly_poisoned", "ignited", "corroded"}
    warning = {"paralyzed", "frozen", "asleep", "confused", "immobile"}
    info = {"tagged", "blinded", "acupunctured", "enfeebled", "weakened"}
    if status_name in danger:
        return "badge-danger"
    if status_name in warning:
        return "badge-warning"
    if status_name in info:
        return "badge-info"
    return "badge-secondary"


@register.simple_tag
def combo_chain_label(chain_length: int, move_names: str) -> str:
    """Format the combo chain display string."""
    return f"Chain x{chain_length} — {move_names}!"


@register.filter
def get_item(dictionary: dict | None, key: object) -> object:
    """Return dictionary[key] or None if the dict is None / key is absent."""
    if dictionary is None:
        return None
    try:
        return dictionary.get(key)
    except (AttributeError, TypeError):
        return None


@register.filter
def is_on_cooldown(value: object) -> bool:
    """Return True if value is a positive integer (move is on cooldown)."""
    try:
        return int(value) > 0  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False


@register.simple_tag
def get_owned_active_moves(owned_pokemon: object) -> list:
    """Return the 4 active (non-passive) assigned moves for an OwnedPokemon.

    Only non-None moves are included. Returns an empty list if owned_pokemon is None.
    """
    if owned_pokemon is None:
        return []
    moves = []
    for m in (
        owned_pokemon.move_standard,
        owned_pokemon.move_chase,
        owned_pokemon.move_special,
        owned_pokemon.move_support,
    ):
        if m is not None:
            moves.append(m)
    return moves
