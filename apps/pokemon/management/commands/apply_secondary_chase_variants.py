"""
Management command: apply_secondary_chase_variants

For every (primary_type, secondary_type) Pokémon combination, creates a
variant chase Move whose applies_status is influenced by the secondary type,
and adds it to each matching species' SpeciesMovePool.

Design rationale
----------------
All chase moves of a given primary type currently share one applies_status
(set by fix_move_types_and_chase).  A Grass Pokémon always applies 'poisoned'
on its chase — but Grass/Fighting (Breloom) should also be able to apply
'paralyzed', while Grass/Psychic (Exeggutor) can apply 'confused'.

Variant moves are ADDED alongside the default chase entries, giving players
more options in the Combo Simulator team builder.

Key properties of a variant move
----------------------------------
- name:           "{Primary} Chase [{Secondary}]"  (unique, identifiable)
- move_type:      primary type  (so it counts as the primary-type chase)
- slot_type:      "chase"
- trigger_status: same as the default trigger for that primary type
- applies_status: secondary-influenced status (the new effect)
- power:          average power of existing primary-type chase moves (min 60)
- combo_starter:  True
- combo_trigger:  True

Idempotency
-----------
Uses get_or_create on the move name, so it is safe to re-run.
SpeciesMovePool entries use get_or_create too (no duplicates).

Usage
-----
    python manage.py apply_secondary_chase_variants
    python manage.py apply_secondary_chase_variants --dry-run
    python manage.py apply_secondary_chase_variants --clear   # remove all variant moves first
"""
from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Default trigger status per primary type (mirrors _TYPE_TRIGGER_STATUS in
# fix_move_types_and_chase, kept here as a string map for readability).
# ---------------------------------------------------------------------------
_PRIMARY_TRIGGER: dict[str, str] = {
    "Fire":     "burned",
    "Water":    "weakened",
    "Electric": "burned",
    "Grass":    "seeded",
    "Ice":      "paralyzed",
    "Fighting": "flinched",
    "Poison":   "confused",
    "Ground":   "paralyzed",
    "Rock":     "flinched",
    "Ghost":    "asleep",
    "Psychic":  "confused",
    "Bug":      "weakened",
    "Dark":     "taunted",
    "Dragon":   "ignited",
    "Normal":   "flinched",
    "Flying":   "airborne",
    "Steel":    "poisoned",
    "Fairy":    "infatuated",
}

# Default applies_status per primary type (mirrors _CHASE_APPLIES_STATUS in
# fix_move_types_and_chase).  Entries equal to this for their primary type
# are skipped — no point creating a variant identical to the default.
_PRIMARY_DEFAULT_APPLIES: dict[str, str] = {
    "Fire":     "ignited",
    "Water":    "confused",
    "Electric": "paralyzed",
    "Grass":    "poisoned",
    "Ice":      "asleep",
    "Fighting": "weakened",
    "Poison":   "poisoned",
    "Ground":   "immobile",
    "Rock":     "airborne",
    "Ghost":    "confused",
    "Psychic":  "imprisoned",
    "Bug":      "confused",
    "Dark":     "confused",
    "Dragon":   "weakened",
    "Normal":   "weakened",
    "Flying":   "weakened",
    "Steel":    "weakened",
    "Fairy":    "chaos",
}

# ---------------------------------------------------------------------------
# Secondary-type chase variant map
# (primary_type, secondary_type) -> applies_status_name
#
# Only entries where the secondary influence produces a DIFFERENT effect from
# _PRIMARY_DEFAULT_APPLIES[primary] are useful; the command skips same-as-
# default entries automatically.
#
# Thematic rules applied:
#   - /Electric secondary  -> paralyzed   (voltage on contact)
#   - /Ice secondary       -> frozen      (cold locks movement)
#   - /Ground secondary    -> immobile    (earth anchors)
#   - /Rock secondary      -> airborne    (impact launches)
#   - /Flying secondary    -> airborne    (flight carries target up)
#   - /Psychic secondary   -> imprisoned  (mind sealed)
#   - /Steel secondary     -> imprisoned  (metal cage) or weakened (drain)
#   - /Dark secondary      -> confused    (shadow tricks)
#   - /Ghost secondary     -> confused    (haunted)
#   - /Poison secondary    -> poisoned    (venom on hit)
#   - /Fire secondary      -> ignited     (heat escalates)
#   - /Fairy secondary     -> chaos       (enchantment breaks will)
#   - /Fighting secondary  -> weakened    (physical overwhelming) or paralyzed
#   - /Water secondary     -> weakened    (washes away) or confused
#   - /Dragon secondary    -> weakened    (raw power overwhelms)
#   - /Bug secondary       -> confused    (swarm disorients)
#   - /Normal secondary    -> weakened    (basic physical)
#   - /Grass secondary     -> poisoned    (spore toxin)
# ---------------------------------------------------------------------------
SECONDARY_CHASE_APPLIES: dict[tuple[str, str], str] = {

    # ── Grass primary (default: seeded → poisoned) ────────────────────────
    ("Grass", "Fighting"):  "paralyzed",  # Breloom, Virizion: vine whip stuns
    ("Grass", "Bug"):       "weakened",   # Paras, Parasect: leeching drains
    ("Grass", "Psychic"):   "confused",   # Exeggutor: spore psychedelia
    ("Grass", "Flying"):    "airborne",   # Jumpluff, Tropius: seed bombs launch
    ("Grass", "Dark"):      "confused",   # Shiftry, Zarude: dark spores disorient
    ("Grass", "Ice"):       "frozen",     # Abomasnow: frost vines
    ("Grass", "Electric"):  "paralyzed",  # Rotom-Mow: electric vines stun
    ("Grass", "Ground"):    "immobile",   # Torterra: earth vines trap
    ("Grass", "Dragon"):    "ignited",    # Alolan Exeggutor: dragon fire vines
    ("Grass", "Ghost"):     "confused",   # Trevenant, Gourgeist: haunted spores
    ("Grass", "Fairy"):     "chaos",      # Whimsicott, Comfey: fairy seed swarm
    ("Grass", "Steel"):     "weakened",   # Ferrothorn: metal drain
    ("Grass", "Water"):     "weakened",   # Ludicolo: water leeching
    ("Grass", "Rock"):      "airborne",   # Cradily: spore-fossil launch
    ("Grass", "Normal"):    "weakened",   # Sawsbuck: basic drain
    ("Grass", "Fire"):      "ignited",    # ??? rare — fire grass escalates burn
    ("Grass", "Poison"):    "poisoned",   # Bulbasaur line — same as default (skipped)

    # ── Fire primary (default: burned → ignited) ──────────────────────────
    ("Fire", "Flying"):     "airborne",   # Charizard, Moltres, Ho-Oh, Talonflame
    ("Fire", "Fighting"):   "weakened",   # Blaziken, Infernape, Emboar
    ("Fire", "Dragon"):     "weakened",   # Reshiram: bridging burn→dragon chain
    ("Fire", "Rock"):       "airborne",   # Magcargo, Camerupt: volcanic launch
    ("Fire", "Ghost"):      "confused",   # Chandelure, Litwick: ghost fire haunts
    ("Fire", "Dark"):       "confused",   # Incineroar, Houndoom: dark tricks
    ("Fire", "Ground"):     "immobile",   # Camerupt (Fire/Ground): lava buries
    ("Fire", "Steel"):      "weakened",   # Heatran: forge overwhelms
    ("Fire", "Psychic"):    "confused",   # Galarian Rapidash: fire enchantment
    ("Fire", "Normal"):     "weakened",   # Pyroar: basic fire beat-down
    ("Fire", "Electric"):   "paralyzed",  # Rotom-Heat: electric surge
    ("Fire", "Water"):      "weakened",   # Volcanion: steam pressure
    ("Fire", "Fairy"):      "chaos",      # Delphox: fire fairy mind control
    ("Fire", "Ice"):        "frozen",     # ??? rare — cold fire paradox
    ("Fire", "Poison"):     "poisoned",   # ??? rare

    # ── Water primary (default: weakened → confused) ──────────────────────
    ("Water", "Ice"):       "frozen",     # Cloyster, Lapras, Walrein
    ("Water", "Electric"):  "paralyzed",  # Lanturn, Rotom-Wash
    ("Water", "Poison"):    "poisoned",   # Tentacruel, Qwilfish
    ("Water", "Ground"):    "immobile",   # Swampert, Gastrodon
    ("Water", "Flying"):    "airborne",   # Gyarados: water jet launches
    ("Water", "Psychic"):   "imprisoned", # Slowbro, Starmie, Slowking
    ("Water", "Rock"):      "airborne",   # Kabutops, Omastar, Barbaracle
    ("Water", "Dark"):      "confused",   # Sharpedo, Crawdaunt (same as default)
    ("Water", "Ghost"):     "confused",   # Jellicent (same as default)
    ("Water", "Fighting"):  "weakened",   # Keldeo: same as default
    ("Water", "Steel"):     "weakened",   # Empoleon: metal overwhelm
    ("Water", "Fairy"):     "chaos",      # Azumarill, Primarina
    ("Water", "Dragon"):    "weakened",   # Kingdra, Palkia: dragon overwhelm
    ("Water", "Fire"):      "ignited",    # Volcanion (reversed emphasis)
    ("Water", "Normal"):    "weakened",   # Bibarel: same as default
    ("Water", "Grass"):     "poisoned",   # Ludicolo (reversed): spore-water

    # ── Electric primary (default: burned → paralyzed) ────────────────────
    ("Electric", "Steel"):  "weakened",   # Magnezone: metal overwhelm
    ("Electric", "Flying"): "airborne",   # Zapdos, Thundurus: thunder launches
    ("Electric", "Ghost"):  "confused",   # Rotom family: haunted circuits
    ("Electric", "Fairy"):  "chaos",      # Tapu Koko: electric fairy mayhem
    ("Electric", "Ice"):    "frozen",     # Rotom-Frost: arctic charge
    ("Electric", "Fire"):   "ignited",    # Rotom-Heat: electric fire escalates
    ("Electric", "Water"):  "weakened",   # Rotom-Wash: electric drain
    ("Electric", "Grass"):  "poisoned",   # Rotom-Mow: electric-spore combo
    ("Electric", "Dragon"): "weakened",   # Zekrom: thundercrash
    ("Electric", "Psychic"):"confused",   # Mega Ampharos: electric distortion
    ("Electric", "Normal"): "weakened",   # Zebstrika: basic shock
    ("Electric", "Ground"): "immobile",   # Stunfisk: electric mud trap
    ("Electric", "Fighting"):"weakened",  # Zeraora: electric fighting

    # ── Ice primary (default: paralyzed → asleep) ─────────────────────────
    ("Ice", "Water"):       "frozen",     # Lapras, Cloyster: deep freeze
    ("Ice", "Ground"):      "immobile",   # Mamoswine, Piloswine: frozen mud
    ("Ice", "Rock"):        "airborne",   # Aurorus: ice spear launches
    ("Ice", "Psychic"):     "confused",   # Jynx: icy psychic daze
    ("Ice", "Ghost"):       "confused",   # Froslass: frozen haunt
    ("Ice", "Steel"):       "weakened",   # Alolan Sandslash: ice armor drain
    ("Ice", "Dragon"):      "weakened",   # Kyurem forms: blizzard overwhelm
    ("Ice", "Fairy"):       "chaos",      # Alolan Ninetales: blizzard enchantment
    ("Ice", "Flying"):      "airborne",   # Articuno: glacial wind lifts
    ("Ice", "Dark"):        "confused",   # Weavile: cold tricks
    ("Ice", "Normal"):      "weakened",   # Delibird, Beartic: basic chill
    ("Ice", "Fighting"):    "weakened",   # Crabominable: ice fighting
    ("Ice", "Poison"):      "poisoned",   # ??? rare
    ("Ice", "Electric"):    "paralyzed",  # Rotom-Frost (reversed)

    # ── Fighting primary (default: flinched → weakened) ───────────────────
    ("Fighting", "Rock"):   "airborne",   # Terrakion: rock + fighting launches
    ("Fighting", "Steel"):  "imprisoned", # Cobalion, Lucario: discipline traps
    ("Fighting", "Dark"):   "confused",   # Pangoro, Scrafty: dark fighting tricks
    ("Fighting", "Psychic"):"imprisoned", # Gallade, Medicham: psychic holds mind
    ("Fighting", "Ice"):    "frozen",     # Crabominable: ice punch cold
    ("Fighting", "Bug"):    "confused",   # Heracross: bug fighting swarm
    ("Fighting", "Fire"):   "ignited",    # Blaziken: fire kick escalates
    ("Fighting", "Flying"): "airborne",   # Hawlucha: fighting flight
    ("Fighting", "Poison"): "poisoned",   # Toxicroak, Croagunk: venom punch
    ("Fighting", "Dragon"): "weakened",   # Kommo-o: fighting dragon
    ("Fighting", "Fairy"):  "chaos",      # ??? rare
    ("Fighting", "Electric"):"paralyzed", # Zeraora: fighting electric
    ("Fighting", "Ghost"):  "confused",   # Marshadow: ghost fighting
    ("Fighting", "Normal"): "weakened",   # Bewear: brute force
    ("Fighting", "Water"):  "confused",   # Keldeo: water wave
    ("Fighting", "Grass"):  "poisoned",   # Breloom: spore punch
    ("Fighting", "Ground"): "immobile",   # ??? earth-fighting pins

    # ── Poison primary (default: confused → poisoned) ─────────────────────
    ("Poison", "Ground"):   "immobile",   # Nidoking/Nidoqueen: venom + earth
    ("Poison", "Flying"):   "airborne",   # Crobat, Golbat: toxic cloud launches
    ("Poison", "Bug"):      "confused",   # Beedrill, Venomoth: bug swarm toxin
    ("Poison", "Dark"):     "confused",   # Drapion: dark venom tricks
    ("Poison", "Fighting"): "weakened",   # Toxicroak: fighting venom drain
    ("Poison", "Water"):    "weakened",   # Tentacruel (reversed): water drain
    ("Poison", "Ghost"):    "confused",   # Gengar (reversed): ghost confusion
    ("Poison", "Dragon"):   "weakened",   # Eternatus, Naganadel: dragon venom
    ("Poison", "Rock"):     "airborne",   # Nihilego: parasite launches
    ("Poison", "Electric"): "paralyzed",  # ??? rare
    ("Poison", "Fire"):     "ignited",    # ??? rare — burning venom
    ("Poison", "Normal"):   "weakened",   # Grimer, Muk: basic toxic drain
    ("Poison", "Steel"):    "weakened",   # ??? rare
    ("Poison", "Fairy"):    "chaos",      # ??? rare
    ("Poison", "Psychic"):  "imprisoned", # ??? rare — psychic + toxin trap
    ("Poison", "Ice"):      "frozen",     # ??? rare — frozen venom

    # ── Ground primary (default: paralyzed → immobile) ────────────────────
    ("Ground", "Rock"):     "airborne",   # Golem, Rhyperior: rock + earth launch
    ("Ground", "Flying"):   "airborne",   # Gliscor, Landorus: earth dive launches
    ("Ground", "Water"):    "confused",   # Gastrodon, Swampert (reversed): muddy
    ("Ground", "Dragon"):   "weakened",   # Garchomp: dragon earth overwhelm
    ("Ground", "Dark"):     "confused",   # Krookodile: dark earth tricks
    ("Ground", "Electric"): "paralyzed",  # Stunfisk: electric mud zap
    ("Ground", "Poison"):   "poisoned",   # Nidoking (reversed): venom burrow
    ("Ground", "Steel"):    "imprisoned", # Steelix: metal earth trap
    ("Ground", "Fire"):     "ignited",    # Camerupt: volcanic eruption
    ("Ground", "Ice"):      "frozen",     # Mamoswine (reversed): frozen earth
    ("Ground", "Ghost"):    "confused",   # Golurk: ghost earth haunts
    ("Ground", "Bug"):      "confused",   # Nincada: underground bug
    ("Ground", "Grass"):    "poisoned",   # Torterra (reversed): earth spores
    ("Ground", "Normal"):   "weakened",   # Diggersby: basic dig
    ("Ground", "Psychic"):  "imprisoned", # ??? rare
    ("Ground", "Fairy"):    "chaos",      # ??? rare

    # ── Rock primary (default: flinched → airborne) ───────────────────────
    ("Rock", "Ground"):     "immobile",   # Golem (reversed): earth pins after launch
    ("Rock", "Water"):      "weakened",   # Kabutops: ancient water drain
    ("Rock", "Steel"):      "imprisoned", # Aggron, Probopass: steel trap
    ("Rock", "Dragon"):     "weakened",   # Tyrunt/Tyrantrum: ancient dragon
    ("Rock", "Fighting"):   "weakened",   # Terrakion (reversed): fighting beat-down
    ("Rock", "Dark"):       "confused",   # Tyranitar: rubble confusion
    ("Rock", "Ice"):        "frozen",     # Aurorus (reversed): ice rock
    ("Rock", "Bug"):        "confused",   # Armaldo, Anorith: fossil bug swarm
    ("Rock", "Psychic"):    "imprisoned", # Solrock, Lunatone: cosmic psychic trap
    ("Rock", "Poison"):     "poisoned",   # Nihilego: parasitic venom
    ("Rock", "Electric"):   "paralyzed",  # ??? rare
    ("Rock", "Grass"):      "poisoned",   # Cradily (reversed): toxic spore fossil
    ("Rock", "Fire"):       "ignited",    # Magcargo (reversed): fire rock
    ("Rock", "Normal"):     "weakened",   # Sudowoodo: basic rock
    ("Rock", "Fairy"):      "chaos",      # ??? rare
    ("Rock", "Ghost"):      "confused",   # ??? rare
    ("Rock", "Flying"):     "airborne",   # Aerodactyl: same as default (skipped)

    # ── Ghost primary (default: asleep → confused) ────────────────────────
    ("Ghost", "Poison"):    "poisoned",   # Gengar: spectral toxin (classic!)
    ("Ghost", "Fire"):      "ignited",    # Chandelure: ghost fire escalates
    ("Ghost", "Steel"):     "weakened",   # Aegislash: ghost blade drain
    ("Ghost", "Dragon"):    "weakened",   # Giratina, Dragapult: overwhelming
    ("Ghost", "Dark"):      "confused",   # Sableye, Spiritomb: same as default
    ("Ghost", "Flying"):    "airborne",   # Drifblim: ghost balloon float launches
    ("Ghost", "Ice"):       "frozen",     # Froslass: ice ghost freeze
    ("Ghost", "Electric"):  "paralyzed",  # Rotom: haunted circuit shocks
    ("Ghost", "Psychic"):   "imprisoned", # Hoopa: psychic ghost trap
    ("Ghost", "Water"):     "confused",   # Jellicent: watery haunt
    ("Ghost", "Ground"):    "immobile",   # Golurk: ghost + earth pins
    ("Ghost", "Grass"):     "poisoned",   # Trevenant (reversed): toxic haunt
    ("Ghost", "Fairy"):     "chaos",      # ??? rare
    ("Ghost", "Fighting"):  "weakened",   # Marshadow: ghost fighting
    ("Ghost", "Normal"):    "weakened",   # ??? odd combo

    # ── Psychic primary (default: confused → imprisoned) ──────────────────
    ("Psychic", "Flying"):  "airborne",   # Natu, Xatu, Lugia: psychic float
    ("Psychic", "Fighting"):"weakened",   # Gallade, Medicham (reversed)
    ("Psychic", "Ghost"):   "confused",   # Hoopa, Musharna: dream confusion
    ("Psychic", "Water"):   "weakened",   # Slowbro (reversed): water weight
    ("Psychic", "Steel"):   "weakened",   # Metagross (reversed): metal overwhelm
    ("Psychic", "Rock"):    "airborne",   # Solrock, Lunatone (reversed): cosmic launch
    ("Psychic", "Fire"):    "ignited",    # Galarian Rapidash (reversed): fire enchant
    ("Psychic", "Ice"):     "frozen",     # Jynx (reversed): icy psychic
    ("Psychic", "Dragon"):  "weakened",   # Latios/Latias (reversed): dragon overwhelm
    ("Psychic", "Fairy"):   "chaos",      # Gardevoir, Mr. Mime: fairy psychic
    ("Psychic", "Normal"):  "weakened",   # Girafarig, Stantler: basic psychic
    ("Psychic", "Grass"):   "poisoned",   # Exeggutor (reversed): spore mind
    ("Psychic", "Dark"):    "confused",   # ??? unusual
    ("Psychic", "Bug"):     "confused",   # Orbeetle: bug swarm psychic
    ("Psychic", "Ground"):  "immobile",   # ??? rare
    ("Psychic", "Electric"):"paralyzed",  # ??? rare
    ("Psychic", "Poison"):  "poisoned",   # ??? rare
    ("Psychic", "Dark"):    "confused",   # ??? rare

    # ── Bug primary (default: weakened → confused) ────────────────────────
    ("Bug", "Poison"):      "poisoned",   # Beedrill, Ariados, Scolipede: venom sting
    ("Bug", "Flying"):      "airborne",   # Beautifly, Yanmega, Masquerain
    ("Bug", "Ghost"):       "confused",   # Shedinja: ghostly bug
    ("Bug", "Steel"):       "imprisoned", # Forretress, Scizor, Durant
    ("Bug", "Electric"):    "paralyzed",  # Galvantula: spider shock
    ("Bug", "Rock"):        "airborne",   # Armaldo, Crustle: fossil launch
    ("Bug", "Fighting"):    "weakened",   # Heracross: brute bug (same as default)
    ("Bug", "Grass"):       "poisoned",   # Wormadam, Leavanny: plant bug toxin
    ("Bug", "Water"):       "confused",   # Surskit: water bug distortion
    ("Bug", "Fire"):        "ignited",    # Volcarona: fire bug escalates
    ("Bug", "Psychic"):     "imprisoned", # Orbeetle, Butterfree: psychic web
    ("Bug", "Dark"):        "confused",   # Vikavolt: dark bug tricks
    ("Bug", "Ground"):      "immobile",   # Nincada: burrow pins
    ("Bug", "Normal"):      "weakened",   # Volbeat, Illumise: basic bug
    ("Bug", "Ice"):         "frozen",     # ??? rare
    ("Bug", "Dragon"):      "weakened",   # ??? rare
    ("Bug", "Fairy"):       "chaos",      # ??? rare

    # ── Dark primary (default: taunted → confused) ────────────────────────
    ("Dark", "Ice"):        "frozen",     # Weavile, Alolan Persian: cold tricks
    ("Dark", "Fighting"):   "weakened",   # Pangoro, Scrafty: fighting overwhelm
    ("Dark", "Rock"):       "airborne",   # Tyranitar: crunch + rock launch
    ("Dark", "Dragon"):     "weakened",   # Hydreigon, Guzzlord: dark overwhelm
    ("Dark", "Steel"):      "imprisoned", # Bisharp, Pawniard: dark steel discipline
    ("Dark", "Flying"):     "airborne",   # Murkrow, Honchkrow: dark swoop
    ("Dark", "Fire"):       "ignited",    # Incineroar, Houndoom: fire escalates
    ("Dark", "Ground"):     "immobile",   # Krookodile: dark earth pins
    ("Dark", "Ghost"):      "confused",   # Sableye, Spiritomb: same as default
    ("Dark", "Bug"):        "confused",   # Drapion: dark bug swarm
    ("Dark", "Water"):      "weakened",   # Sharpedo, Crawdaunt: dark current
    ("Dark", "Poison"):     "poisoned",   # Drapion (reversed): dark venom
    ("Dark", "Grass"):      "poisoned",   # Cacturne, Shiftry: dark spores
    ("Dark", "Psychic"):    "imprisoned", # ??? unusual — dark psychic trap
    ("Dark", "Electric"):   "paralyzed",  # Zeraora (reversed): dark electric
    ("Dark", "Normal"):     "weakened",   # Absol, Mightyena: dark basic
    ("Dark", "Fairy"):      "chaos",      # ??? rare (narrative: dark corrupts fairy)

    # ── Dragon primary (default: ignited → weakened) ──────────────────────
    ("Dragon", "Flying"):   "airborne",   # Dragonite, Salamence, Rayquaza
    ("Dragon", "Ground"):   "immobile",   # Garchomp: earth anchor
    ("Dragon", "Electric"): "paralyzed",  # Zekrom: lightning crash
    ("Dragon", "Ice"):      "frozen",     # Kyurem forms: blizzard
    ("Dragon", "Psychic"):  "imprisoned", # Latios/Latias, Dragalge: psychic hold
    ("Dragon", "Ghost"):    "confused",   # Dragapult, Giratina: ghost unnerve
    ("Dragon", "Steel"):    "imprisoned", # Dialga: time-steel trap
    ("Dragon", "Fire"):     "ignited",    # Reshiram: fire escalation (same as default! skipped)
    ("Dragon", "Water"):    "confused",   # Kingdra, Palkia: water disorientation
    ("Dragon", "Fighting"): "weakened",   # Kommo-o: fighting overwhelm (same as default)
    ("Dragon", "Dark"):     "confused",   # Hydreigon: dark unnerve
    ("Dragon", "Rock"):     "airborne",   # Tyrunt/Tyrantrum: ancient launch
    ("Dragon", "Grass"):    "poisoned",   # Alolan Exeggutor: tropical spores
    ("Dragon", "Fairy"):    "chaos",      # ??? rare
    ("Dragon", "Poison"):   "poisoned",   # Eternatus, Naganadel: space venom
    ("Dragon", "Normal"):   "weakened",   # ??? rare (same as default)
    ("Dragon", "Bug"):      "confused",   # ??? rare

    # ── Normal primary (default: flinched → weakened) ─────────────────────
    ("Normal", "Flying"):   "airborne",   # Pidgeot, Staraptor, Swellow
    ("Normal", "Psychic"):  "imprisoned", # Girafarig, Musharna-N
    ("Normal", "Ground"):   "immobile",   # Diggersby: earth trap
    ("Normal", "Fire"):     "ignited",    # Pyroar: fire escalation
    ("Normal", "Ice"):      "frozen",     # Delibird, Beartic-N
    ("Normal", "Water"):    "confused",   # Bibarel: water disorientation
    ("Normal", "Rock"):     "airborne",   # Sudowoodo: rock launch
    ("Normal", "Ghost"):    "confused",   # ??? unusual
    ("Normal", "Dark"):     "confused",   # Mightyena-N (reversed): dark tricks
    ("Normal", "Grass"):    "poisoned",   # Sawsbuck: plant spores
    ("Normal", "Dragon"):   "weakened",   # ??? rare (same as default)
    ("Normal", "Fairy"):    "chaos",      # Clefable, Wigglytuff: fairy chaos
    ("Normal", "Bug"):      "confused",   # Volbeat (reversed): bug normal
    ("Normal", "Poison"):   "poisoned",   # ??? rare
    ("Normal", "Steel"):    "imprisoned", # ??? rare
    ("Normal", "Fighting"): "weakened",   # Meloetta: same as default
    ("Normal", "Electric"): "paralyzed",  # Togedemaru-N: ??? rare

    # ── Flying primary (default: airborne → weakened) ─────────────────────
    ("Flying", "Electric"): "paralyzed",  # Zapdos, Thundurus: lightning strike
    ("Flying", "Fire"):     "ignited",    # Moltres, Ho-Oh, Talonflame: fire escalates
    ("Flying", "Ice"):      "frozen",     # Articuno: glacial descent
    ("Flying", "Steel"):    "imprisoned", # Skarmory: steel cage from above
    ("Flying", "Dragon"):   "weakened",   # Dragonite (reversed): dragon air (same as default)
    ("Flying", "Water"):    "confused",   # Gyarados: tidal wave
    ("Flying", "Psychic"):  "imprisoned", # Lugia, Xatu: psychic cage
    ("Flying", "Dark"):     "confused",   # Murkrow (reversed): dark air tricks
    ("Flying", "Fighting"): "weakened",   # Hawlucha: fighting (same as default)
    ("Flying", "Bug"):      "confused",   # Beautifly (reversed): bug air swarm
    ("Flying", "Ghost"):    "confused",   # Drifblim (reversed): ghost air haunt
    ("Flying", "Poison"):   "poisoned",   # Crobat (reversed): toxic gas cloud
    ("Flying", "Grass"):    "poisoned",   # Tropius, Jumpluff (reversed): pollen
    ("Flying", "Normal"):   "weakened",   # Pidgey (reversed): same as default
    ("Flying", "Fairy"):    "chaos",      # Togekiss: fairy enchantment above
    ("Flying", "Ground"):   "immobile",   # Gliscor (reversed): dive pins
    ("Flying", "Rock"):     "airborne",   # Aerodactyl: same as default (skipped)

    # ── Steel primary (default: poisoned → weakened) ──────────────────────
    ("Steel", "Ground"):    "immobile",   # Steelix, Excadrill: metal earth anchor
    ("Steel", "Electric"):  "paralyzed",  # Magnezone: electric steel shock
    ("Steel", "Psychic"):   "imprisoned", # Metagross, Bronzong, Jirachi
    ("Steel", "Rock"):      "airborne",   # Aggron: metal rock launch
    ("Steel", "Dark"):      "imprisoned", # Bisharp, Pawniard: dark steel discipline
    ("Steel", "Flying"):    "airborne",   # Skarmory (reversed): steel flight
    ("Steel", "Ghost"):     "confused",   # Aegislash: ghost blade haunts
    ("Steel", "Ice"):       "frozen",     # Alolan Sandslash (reversed): ice armor
    ("Steel", "Fire"):      "ignited",    # Heatran (reversed): forge fire escalates
    ("Steel", "Water"):     "weakened",   # Empoleon (reversed): same as default
    ("Steel", "Bug"):       "confused",   # Durant, Scizor (reversed): bug swarm
    ("Steel", "Grass"):     "poisoned",   # Ferrothorn: thorny drain
    ("Steel", "Dragon"):    "weakened",   # Dialga (reversed): same as default
    ("Steel", "Fairy"):     "chaos",      # Magearna: fairy steel magic
    ("Steel", "Normal"):    "weakened",   # ??? same as default
    ("Steel", "Fighting"):   "weakened",  # Lucario (reversed): same as default
    ("Steel", "Poison"):    "poisoned",   # ??? rare

    # ── Fairy primary (default: infatuated → chaos) ───────────────────────
    # Chaos is the signature Fairy terminal; some combos get alternate effects
    ("Fairy", "Psychic"):   "imprisoned", # Gardevoir, Mr. Mime: psychic trap instead
    ("Fairy", "Steel"):     "imprisoned", # Magearna (reversed): steel discipline
    ("Fairy", "Flying"):    "airborne",   # Togekiss: fairy flight launch
    ("Fairy", "Water"):     "weakened",   # Azumarill, Primarina: water drain
    ("Fairy", "Ice"):       "frozen",     # Alolan Ninetales: blizzard enchantment
    ("Fairy", "Electric"):  "paralyzed",  # Tapu Koko (reversed): electric surge
    ("Fairy", "Fire"):      "ignited",    # Delphox (reversed): fire escalation
    ("Fairy", "Grass"):     "poisoned",   # Whimsicott (reversed): spore
    ("Fairy", "Dark"):      "confused",   # ??? rare — dark corrupts the enchantment
    ("Fairy", "Normal"):    "weakened",   # Clefable, Wigglytuff: normal fairy
    ("Fairy", "Dragon"):    "weakened",   # ??? fairy counters dragon — weakens
    ("Fairy", "Fighting"):   "weakened",  # ??? rare
    ("Fairy", "Ghost"):     "confused",   # ??? rare
    ("Fairy", "Bug"):       "confused",   # ??? rare
    ("Fairy", "Poison"):    "poisoned",   # ??? rare (Poison counters Fairy)
    ("Fairy", "Rock"):      "airborne",   # ??? rare
    ("Fairy", "Ground"):    "immobile",   # ??? rare
}


# ---------------------------------------------------------------------------
# Thematic move names for every (primary, secondary) combination.
# Naming rules:
#   Primary type = the element / material of the move  (vine, ember, shadow…)
#   Secondary type = the delivery mechanic / flavor    (kick, fang, dive, haunt…)
#   Applied status also shapes the name where possible:
#     airborne  → launch/dive/burst/float
#     immobile  → trap/anchor/burrow
#     imprisoned → lock/cage/discipline/edge
#     chaos     → charm/storm/rush
#     frozen    → frost… / deep freeze / blizzard
# Every name is unique across the full table.
# ---------------------------------------------------------------------------
VARIANT_MOVE_NAMES: dict[tuple[str, str], str] = {
    # ── Bug ──────────────────────────────────────────────────────────────────
    ("Bug", "Electric"):  "Spark Sting",
    ("Bug", "Fairy"):     "Pixie Swarm",
    ("Bug", "Fire"):      "Ember Swarm",
    ("Bug", "Flying"):    "Swarm Dive",
    ("Bug", "Grass"):     "Spore Bite",
    ("Bug", "Ground"):    "Sand Burrow",
    ("Bug", "Poison"):    "Venom Sting",
    ("Bug", "Psychic"):   "Mind Web",
    ("Bug", "Rock"):      "Stone Launch",
    ("Bug", "Steel"):     "Iron Cocoon",

    # ── Dark ─────────────────────────────────────────────────────────────────
    ("Dark", "Dragon"):   "Dragon Fang",
    ("Dark", "Fairy"):    "Nightmare Charm",
    ("Dark", "Fighting"): "Shadow Strike",
    ("Dark", "Fire"):     "Dark Ember",
    ("Dark", "Flying"):   "Shadow Wing",
    ("Dark", "Grass"):    "Night Spore",
    ("Dark", "Ice"):      "Frost Bite",
    ("Dark", "Normal"):   "Shadow Rake",
    ("Dark", "Poison"):   "Toxic Fang",
    ("Dark", "Psychic"):  "Mind Trap",
    ("Dark", "Steel"):    "Iron Grudge",

    # ── Dragon ───────────────────────────────────────────────────────────────
    ("Dragon", "Electric"): "Thunder Scale",
    ("Dragon", "Flying"):   "Sky Fang",
    ("Dragon", "Ghost"):    "Phantom Roar",
    ("Dragon", "Ground"):   "Earth Fang",
    ("Dragon", "Ice"):      "Frost Scale",
    ("Dragon", "Psychic"):  "Mind Break",
    ("Dragon", "Water"):    "Tidal Fang",

    # ── Electric ─────────────────────────────────────────────────────────────
    ("Electric", "Dragon"): "Volt Crash",
    ("Electric", "Fairy"):  "Spark Charm",
    ("Electric", "Flying"): "Volt Dive",
    ("Electric", "Ghost"):  "Static Haunt",
    ("Electric", "Ice"):    "Frost Shock",
    ("Electric", "Normal"): "Zap Tackle",
    ("Electric", "Steel"):  "Iron Discharge",

    # ── Fairy ────────────────────────────────────────────────────────────────
    ("Fairy", "Flying"):    "Petal Float",

    # ── Fighting ─────────────────────────────────────────────────────────────
    ("Fighting", "Dark"):    "Shadow Uppercut",
    ("Fighting", "Flying"):  "Rising Kick",
    ("Fighting", "Ghost"):   "Spirit Cross",
    ("Fighting", "Ice"):     "Frost Slam",
    ("Fighting", "Poison"):  "Venom Strike",
    ("Fighting", "Psychic"): "Mind Lock",
    ("Fighting", "Steel"):   "Iron Discipline",

    # ── Fire ─────────────────────────────────────────────────────────────────
    ("Fire", "Dark"):     "Shadow Ember",
    ("Fire", "Dragon"):   "Dragon Fire",
    ("Fire", "Fighting"): "Ember Slam",
    ("Fire", "Flying"):   "Sky Ember",
    ("Fire", "Ghost"):    "Spirit Flame",
    ("Fire", "Ground"):   "Lava Trap",
    ("Fire", "Normal"):   "Flame Tackle",
    ("Fire", "Psychic"):  "Mystic Flame",
    ("Fire", "Rock"):     "Magma Launch",
    ("Fire", "Steel"):    "Forge Strike",
    ("Fire", "Water"):    "Steam Surge",

    # ── Flying ───────────────────────────────────────────────────────────────
    ("Flying", "Steel"):  "Steel Dive",
    ("Flying", "Water"):  "Aqua Wing",

    # ── Ghost ────────────────────────────────────────────────────────────────
    ("Ghost", "Dragon"):  "Dragon Hex",
    ("Ghost", "Fairy"):   "Phantom Charm",
    ("Ghost", "Fire"):    "Hex Fire",
    ("Ghost", "Flying"):  "Phantom Wing",
    ("Ghost", "Grass"):   "Spore Haunt",
    ("Ghost", "Ground"):  "Grave Trap",
    ("Ghost", "Poison"):  "Hex Venom",

    # ── Grass ────────────────────────────────────────────────────────────────
    ("Grass", "Dark"):    "Shadow Spore",
    ("Grass", "Dragon"):  "Dragon Bloom",
    ("Grass", "Fairy"):   "Petal Storm",
    ("Grass", "Fighting"): "Spore Kick",
    ("Grass", "Flying"):  "Seed Burst",
    ("Grass", "Ghost"):   "Phantom Root",
    ("Grass", "Ground"):  "Root Trap",
    ("Grass", "Ice"):     "Frost Vine",
    ("Grass", "Psychic"): "Dream Spore",
    ("Grass", "Steel"):   "Iron Thorn",

    # ── Ground ───────────────────────────────────────────────────────────────
    ("Ground", "Dark"):    "Sand Shadow",
    ("Ground", "Dragon"):  "Dragon Quake",
    ("Ground", "Flying"):  "Dust Launch",
    ("Ground", "Ghost"):   "Grave Haunt",
    ("Ground", "Normal"):  "Sand Tackle",
    ("Ground", "Psychic"): "Mind Burrow",
    ("Ground", "Rock"):    "Rock Launch",
    ("Ground", "Steel"):   "Iron Quake",

    # ── Ice ──────────────────────────────────────────────────────────────────
    ("Ice", "Flying"):   "Frost Launch",
    ("Ice", "Ghost"):    "Frost Haunt",
    ("Ice", "Ground"):   "Glacier Trap",
    ("Ice", "Psychic"):  "Mind Freeze",
    ("Ice", "Water"):    "Deep Freeze",

    # ── Normal ───────────────────────────────────────────────────────────────
    ("Normal", "Fairy"):   "Charm Rush",
    ("Normal", "Flying"):  "Wing Tackle",
    ("Normal", "Grass"):   "Spore Slam",
    ("Normal", "Ground"):  "Mud Tackle",
    ("Normal", "Psychic"): "Mind Slam",
    ("Normal", "Water"):   "Splash Rush",

    # ── Poison ───────────────────────────────────────────────────────────────
    ("Poison", "Dragon"):   "Venom Fang",
    ("Poison", "Fighting"): "Toxic Strike",
    ("Poison", "Fire"):     "Acid Burn",
    ("Poison", "Flying"):   "Spore Cloud",
    ("Poison", "Ground"):   "Venom Trap",
    ("Poison", "Water"):    "Acid Current",

    # ── Psychic ──────────────────────────────────────────────────────────────
    ("Psychic", "Fairy"):    "Dream Charm",
    ("Psychic", "Fighting"): "Psycho Strike",
    ("Psychic", "Fire"):     "Mystic Fire",
    ("Psychic", "Flying"):   "Psycho Float",
    ("Psychic", "Grass"):    "Spore Mind",
    ("Psychic", "Normal"):   "Zen Tackle",
    ("Psychic", "Steel"):    "Iron Mind",

    # ── Rock ─────────────────────────────────────────────────────────────────
    ("Rock", "Bug"):      "Swarm Stone",
    ("Rock", "Dark"):     "Shadow Rock",
    ("Rock", "Dragon"):   "Dragon Stone",
    ("Rock", "Fairy"):    "Crystal Charm",
    ("Rock", "Fighting"): "Stone Strike",
    ("Rock", "Fire"):     "Magma Stone",
    ("Rock", "Grass"):    "Spore Stone",
    ("Rock", "Ground"):   "Bedrock Slam",
    ("Rock", "Ice"):      "Frost Stone",
    ("Rock", "Poison"):   "Toxic Rock",
    ("Rock", "Psychic"):  "Mind Stone",
    ("Rock", "Steel"):    "Iron Boulder",
    ("Rock", "Water"):    "Tidal Stone",

    # ── Steel ────────────────────────────────────────────────────────────────
    ("Steel", "Fairy"):   "Crystal Edge",
    ("Steel", "Flying"):  "Sky Blade",
    ("Steel", "Ghost"):   "Phantom Edge",
    ("Steel", "Ground"):  "Iron Anchor",
    ("Steel", "Psychic"): "Psychic Edge",
    ("Steel", "Rock"):    "Metal Launch",

    # ── Water ────────────────────────────────────────────────────────────────
    ("Water", "Electric"): "Shock Current",
    ("Water", "Fairy"):    "Aqua Charm",
    ("Water", "Flying"):   "Aqua Dive",
    ("Water", "Grass"):    "Toxic Current",
    ("Water", "Ground"):   "Mud Current",
    ("Water", "Ice"):      "Blizzard Current",
    ("Water", "Poison"):   "Venom Current",
    ("Water", "Psychic"):  "Psychic Wave",
    ("Water", "Rock"):     "Tidal Launch",
}


class Command(BaseCommand):
    help = (
        "Create secondary-type-influenced variant chase moves and add them "
        "to matching species' SpeciesMovePool entries."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Preview changes without writing to the database.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            default=False,
            help="Remove all previously created variant moves (name contains ' Chase [') before re-running.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from apps.effects.models import StatusEffect
        from apps.pokemon.models import Move, Pokemon, PokemonType, SpeciesMovePool

        dry_run: bool = options["dry_run"]
        clear: bool = options["clear"]

        self.stdout.write(self.style.MIGRATE_HEADING("=== apply_secondary_chase_variants ==="))
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be written."))

        with transaction.atomic():

            # ------------------------------------------------------------------
            # Optional clear: remove all variant moves previously created
            # ------------------------------------------------------------------
            if clear:
                # Match both old-style "Grass Chase [Fighting]" AND new thematic names
                all_variant_names = set(VARIANT_MOVE_NAMES.values())
                variant_qs = Move.objects.filter(
                    name__in=all_variant_names
                ) | Move.objects.filter(name__contains=" Chase [")
                if not dry_run:
                    # Pool entries referencing these moves cascade via FK if protected,
                    # so remove pool entries first.
                    pool_deleted, _ = SpeciesMovePool.objects.filter(
                        move__in=variant_qs
                    ).delete()
                    move_deleted, _ = variant_qs.delete()
                    self.stdout.write(
                        self.style.WARNING(
                            f"  --clear: removed {move_deleted} variant moves "
                            f"and {pool_deleted} pool entries."
                        )
                    )
                else:
                    count = variant_qs.count()
                    self.stdout.write(
                        f"  [dry-run] --clear would remove {count} variant moves."
                    )

            # ------------------------------------------------------------------
            # Build lookup tables
            # ------------------------------------------------------------------
            status_by_name: dict[str, StatusEffect] = {
                s.name: s for s in StatusEffect.objects.all()
            }
            type_by_name: dict[str, PokemonType] = {
                t.name: t for t in PokemonType.objects.all()
            }

            # Average power of existing chase moves per primary type
            existing_chase_moves = list(
                Move.objects.filter(slot_type="chase")
                .exclude(name__contains=" Chase [")  # exclude any prior variants
                .select_related("move_type")
            )
            type_chase_power: dict[str, int] = {}
            type_chase_count: dict[str, int] = {}
            for m in existing_chase_moves:
                tname = m.move_type.name
                type_chase_power[tname] = type_chase_power.get(tname, 0) + m.power
                type_chase_count[tname] = type_chase_count.get(tname, 0) + 1
            avg_power: dict[str, int] = {
                t: max(60, type_chase_power[t] // type_chase_count[t])
                for t in type_chase_count
            }

            # All species with both a primary AND a secondary type
            species_with_dual_type = list(
                Pokemon.objects
                .filter(
                    pokedex_number__isnull=False,
                    secondary_type__isnull=False,
                )
                .select_related("primary_type", "secondary_type")
            )

            # Index species by (primary_type_name, secondary_type_name)
            from collections import defaultdict
            species_by_combo: dict[tuple[str, str], list[Pokemon]] = defaultdict(list)
            for sp in species_with_dual_type:
                key = (sp.primary_type.name, sp.secondary_type.name)
                species_by_combo[key].append(sp)

            # Existing pool entries indexed by (species_id, move_id) for fast lookup
            existing_pool: set[tuple[int, int]] = set(
                SpeciesMovePool.objects.filter(slot_type="chase")
                .values_list("species_id", "move_id")
            )

            # ------------------------------------------------------------------
            # Main loop: create variant moves + pool entries
            # ------------------------------------------------------------------
            total_moves_created = 0
            total_pool_entries = 0
            skipped_same_as_default = 0
            skipped_no_status = 0
            skipped_no_species = 0

            for (primary_name, secondary_name), applies_name in SECONDARY_CHASE_APPLIES.items():

                # Skip if variant effect == default for this primary type
                default_applies = _PRIMARY_DEFAULT_APPLIES.get(primary_name)
                if applies_name == default_applies:
                    skipped_same_as_default += 1
                    continue

                # Resolve trigger status first so we can check for self-loops
                trigger_name = _PRIMARY_TRIGGER.get(primary_name)
                trigger_obj = status_by_name.get(trigger_name) if trigger_name else None
                if trigger_obj is None:
                    logger.warning(
                        "No trigger status for primary '%s' — skipping.", primary_name
                    )
                    continue

                # Skip if variant effect == trigger (self-loop: fires on X, applies X again)
                if applies_name == trigger_name:
                    skipped_same_as_default += 1
                    continue

                # Validate applies status exists in DB
                status_obj = status_by_name.get(applies_name)
                if status_obj is None:
                    logger.warning(
                        "StatusEffect '%s' not found — skipping (%s, %s).",
                        applies_name, primary_name, secondary_name,
                    )
                    skipped_no_status += 1
                    continue

                # Validate primary type exists
                primary_type_obj = type_by_name.get(primary_name)
                if primary_type_obj is None:
                    logger.warning("PokemonType '%s' not found — skipping.", primary_name)
                    continue

                # Find matching species
                matched_species = species_by_combo.get((primary_name, secondary_name), [])
                if not matched_species:
                    skipped_no_species += 1
                    continue

                # Get or create the variant Move — use thematic name from table
                move_name = VARIANT_MOVE_NAMES.get(
                    (primary_name, secondary_name),
                    f"{primary_name} Chase [{secondary_name}]",  # fallback if table missing entry
                )
                power = avg_power.get(primary_name, 65)

                if not dry_run:
                    variant_move, created = Move.objects.get_or_create(
                        name=move_name,
                        defaults={
                            "move_type": primary_type_obj,
                            "slot_type": "chase",
                            "trigger_status": trigger_obj,
                            "applies_status": status_obj,
                            "power": power,
                            "accuracy": 100,
                            "pp": 10,
                            "combo_starter": True,
                            "combo_trigger": True,
                        },
                    )
                    if not created:
                        # Update applies_status in case the mapping changed
                        if variant_move.applies_status_id != status_obj.pk:
                            variant_move.applies_status = status_obj
                            variant_move.save(update_fields=["applies_status"])
                    if created:
                        total_moves_created += 1
                else:
                    # Dry run: just count
                    exists = Move.objects.filter(name=move_name).exists()
                    if not exists:
                        total_moves_created += 1
                    variant_move = None  # type: ignore[assignment]

                # Add variant move to each matching species' pool
                for species in matched_species:
                    if not dry_run and variant_move is not None:
                        key = (species.pk, variant_move.pk)
                        if key not in existing_pool:
                            SpeciesMovePool.objects.get_or_create(
                                species=species,
                                move=variant_move,
                                defaults={"slot_type": "chase"},
                            )
                            existing_pool.add(key)
                            total_pool_entries += 1
                    else:
                        total_pool_entries += 1

                if dry_run:
                    self.stdout.write(
                        f"  [dry-run] '{move_name}' "
                        f"trigger:{trigger_name} -> applies:{applies_name} "
                        f"for {len(matched_species)} species"
                    )

            # ------------------------------------------------------------------
            # Summary
            # ------------------------------------------------------------------
            if not dry_run:
                self.stdout.write(self.style.SUCCESS(
                    f"  Variant moves created:       {total_moves_created}"
                ))
                self.stdout.write(self.style.SUCCESS(
                    f"  Pool entries added:          {total_pool_entries}"
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"  [dry-run] Would create up to {total_moves_created} new variant moves"
                ))
                self.stdout.write(self.style.SUCCESS(
                    f"  [dry-run] Would add up to    {total_pool_entries} pool entries"
                ))

            self.stdout.write(
                f"  Skipped (same as default):   {skipped_same_as_default}"
            )
            self.stdout.write(
                f"  Skipped (no matching species): {skipped_no_species}"
            )

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS("=== apply_secondary_chase_variants complete ==="))
