"""
Type effectiveness data for the in-game type chart (GDD Section 8.4 / 20.14).

Canonical source: the _SUPER_EFFECTIVE dict in apps/game/ai.py.
This module extends it with not-very-effective and immune relationships,
and exposes helpers for the TypeChartView.

All 18 standard Pokemon types are covered.
"""

# Types that are super-effective against each defender type.
# Key = attacking type, Value = list of defending types it hits for ×2.
SUPER_EFFECTIVE: dict[str, list[str]] = {
    "Normal":   [],
    "Fire":     ["Grass", "Ice", "Bug", "Steel"],
    "Water":    ["Fire", "Rock", "Ground"],
    "Electric": ["Water", "Flying"],
    "Grass":    ["Water", "Rock", "Ground"],
    "Ice":      ["Grass", "Ground", "Flying", "Dragon"],
    "Fighting": ["Normal", "Ice", "Rock", "Dark", "Steel"],
    "Poison":   ["Grass", "Fairy"],
    "Ground":   ["Fire", "Electric", "Poison", "Rock", "Steel"],
    "Flying":   ["Grass", "Fighting", "Bug"],
    "Psychic":  ["Fighting", "Poison"],
    "Bug":      ["Grass", "Psychic", "Dark"],
    "Rock":     ["Fire", "Ice", "Flying", "Bug"],
    "Ghost":    ["Psychic", "Ghost"],
    "Dragon":   ["Dragon"],
    "Dark":     ["Psychic", "Ghost"],
    "Steel":    ["Ice", "Rock", "Fairy"],
    "Fairy":    ["Fighting", "Dragon", "Dark"],
}

# Attacking type → list of defending types it hits for ×0.5.
NOT_VERY_EFFECTIVE: dict[str, list[str]] = {
    "Normal":   ["Rock", "Steel"],
    "Fire":     ["Fire", "Water", "Rock", "Dragon"],
    "Water":    ["Water", "Grass", "Dragon"],
    "Electric": ["Electric", "Grass", "Dragon"],
    "Grass":    ["Fire", "Grass", "Poison", "Flying", "Bug", "Dragon", "Steel"],
    "Ice":      ["Water", "Ice", "Steel"],
    "Fighting": ["Poison", "Bug", "Psychic", "Flying", "Fairy"],
    "Poison":   ["Poison", "Ground", "Rock", "Ghost"],
    "Ground":   ["Grass", "Bug"],
    "Flying":   ["Electric", "Rock", "Steel"],
    "Psychic":  ["Psychic", "Steel"],
    "Bug":      ["Fire", "Fighting", "Flying", "Ghost", "Steel", "Fairy"],
    "Rock":     ["Fighting", "Ground", "Steel"],
    "Ghost":    ["Dark"],
    "Dragon":   ["Steel"],
    "Dark":     ["Fighting", "Dark", "Fairy"],
    "Steel":    ["Fire", "Water", "Electric", "Steel"],
    "Fairy":    ["Fire", "Poison", "Steel"],
}

# Attacking type → list of defending types it does 0 damage to (immune).
IMMUNE: dict[str, list[str]] = {
    "Normal":   ["Ghost"],
    "Fire":     [],
    "Water":    [],
    "Electric": ["Ground"],
    "Grass":    [],
    "Ice":      [],
    "Fighting": ["Ghost"],
    "Poison":   ["Steel"],
    "Ground":   ["Flying"],
    "Flying":   [],
    "Psychic":  ["Dark"],
    "Bug":      [],
    "Rock":     [],
    "Ghost":    ["Normal"],
    "Dragon":   [],
    "Dark":     [],
    "Steel":    [],
    "Fairy":    [],
}

# Ordered list of all 18 types (display order).
ALL_TYPES: list[str] = [
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice",
    "Fighting", "Poison", "Ground", "Flying", "Psychic", "Bug",
    "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy",
]

# CSS colour tokens for type pills — shared with pokemon_detail.html conventions.
TYPE_COLORS: dict[str, dict[str, str]] = {
    "Normal":   {"bg": "#374151", "text": "#e5e7eb"},
    "Fire":     {"bg": "#7f1d1d", "text": "#fca5a5"},
    "Water":    {"bg": "#1e3a5f", "text": "#93c5fd"},
    "Electric": {"bg": "#78350f", "text": "#fcd34d"},
    "Grass":    {"bg": "#14532d", "text": "#86efac"},
    "Ice":      {"bg": "#164e63", "text": "#a5f3fc"},
    "Fighting": {"bg": "#7c2d12", "text": "#fdba74"},
    "Poison":   {"bg": "#581c87", "text": "#d8b4fe"},
    "Ground":   {"bg": "#713f12", "text": "#fde68a"},
    "Flying":   {"bg": "#1e3a8a", "text": "#c7d2fe"},
    "Psychic":  {"bg": "#4a044e", "text": "#f0abfc"},
    "Bug":      {"bg": "#365314", "text": "#bef264"},
    "Rock":     {"bg": "#44403c", "text": "#d6d3d1"},
    "Ghost":    {"bg": "#312e81", "text": "#c4b5fd"},
    "Dragon":   {"bg": "#1e3a8a", "text": "#93c5fd"},
    "Dark":     {"bg": "#1c1917", "text": "#a8a29e"},
    "Steel":    {"bg": "#334155", "text": "#cbd5e1"},
    "Fairy":    {"bg": "#831843", "text": "#fbcfe8"},
}


def get_effectiveness(attacking: str, defending: str) -> float:
    """
    Return the damage multiplier when *attacking* type hits *defending* type.
    Returns 2.0, 0.5, 0.0, or 1.0.
    """
    if defending in IMMUNE.get(attacking, []):
        return 0.0
    if defending in SUPER_EFFECTIVE.get(attacking, []):
        return 2.0
    if defending in NOT_VERY_EFFECTIVE.get(attacking, []):
        return 0.5
    return 1.0


def build_chart_matrix() -> list[dict]:
    """
    Build the full 18×18 effectiveness matrix for template rendering.

    Returns a list of row dicts:
      {
        "attacker": str,               # attacking type name
        "color": {"bg": ..., "text": ...},
        "cells": [
          {"defender": str, "mult": float, "label": str, "css": str},
          ...
        ]
      }
    """
    rows = []
    for attacker in ALL_TYPES:
        cells = []
        for defender in ALL_TYPES:
            mult = get_effectiveness(attacker, defender)
            if mult == 2.0:
                label, css = "2×", "chart-se"
            elif mult == 0.5:
                label, css = "½", "chart-nve"
            elif mult == 0.0:
                label, css = "0", "chart-immune"
            else:
                label, css = "1", "chart-neutral"
            cells.append({"defender": defender, "mult": mult, "label": label, "css": css})
        rows.append({
            "attacker": attacker,
            "color": TYPE_COLORS.get(attacker, {"bg": "#374151", "text": "#e5e7eb"}),
            "cells": cells,
        })
    return rows
