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


_PHYSICAL_ICON: dict[str, str] = {
    "airborne":  "🌀",
    "launched":  "⬆",
    "knockback": "💨",
    "grounded":  "⬇",
}

_UTILITY_ICON: dict[str, str] = {
    "shielded":      "🛡",
    "hidden":        "👁",
    "immune":        "✦",
    "chain_breaker": "⛓",
    "state_locked":  "🔒",
    "charging":      "⚡",
}


@register.filter
def status_badge_class(status_name: str) -> str:
    """Return a CSS badge class for a given status name."""
    danger = {"burned", "poisoned", "badly_poisoned", "ignited", "corroded"}
    warning = {"paralyzed", "frozen", "asleep", "confused", "immobile",
               "infatuated", "acupunctured", "taunted", "seeded"}
    info = {"tagged", "blinded", "enfeebled", "weakened", "interrupted"}
    if status_name in danger:
        return "badge-danger"
    if status_name in warning:
        return "badge-warning"
    if status_name in info:
        return "badge-info"
    if status_name in _PHYSICAL_ICON:
        return f"badge-physical badge-phys-{status_name}"
    if status_name in _UTILITY_ICON:
        return f"badge-utility badge-util-{status_name}"
    return "badge-secondary"


@register.filter
def status_icon(status_name: str) -> str:
    """Return an icon character for a given status name."""
    return _PHYSICAL_ICON.get(status_name) or _UTILITY_ICON.get(status_name, "")


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


@register.filter
def chakra_fill(remaining: object, total_cooldown: object) -> int:
    """
    Return the chakra bar fill percentage (0–100) from cooldown remaining and total.

    When remaining == 0 the bar is full (100%).
    When remaining == total_cooldown the bar is empty (0%).
    """
    try:
        r = int(remaining)  # type: ignore[arg-type]
        t = int(total_cooldown)  # type: ignore[arg-type]
        if t <= 0:
            return 100
        return max(0, min(100, round((1 - r / t) * 100)))
    except (TypeError, ValueError):
        return 0


@register.filter
def min_five(value: object) -> int:
    """Clamp value to max 5 (for chain-link CSS class depth)."""
    try:
        return min(int(value), 5)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


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
