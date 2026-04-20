"""
Management command: fix_move_types_and_chase

Corrects systematic type misassignments in the move fixture and ensures
every chase move applies a status effect so the team chain-trigger system
works correctly.

Background
----------
The original moves.json used a non-standard type numbering that caused:
  - Fairy moves  to stored as Dragon  (DB type 15)   fix: to Fairy  (18)
  - Dragon moves to stored as Rock    (DB type 13)   fix: to Dragon (15)
  - Rock moves   to stored as Ground  (DB type  9)   fix: to Rock   (13)
  - Dark moves   to stored as Bug     (DB type 12)   fix: to Dark   (16)
  - Flying moves to stored as Normal  (DB type  1)   fix: to Flying (10)
  - Steel moves  to stored as Normal  (DB type  1)   fix: to Steel  (17)

Chain-trigger mechanic
----------------------
Each Chase move must apply a status so that a second Pokemon's Chase can
auto-fire in response.  This creates multi-Pokemon combo chains.

  Standard (applies burned)
    to Chase A fires  (trigger_status=burned, also applies confused)
      to Chase B fires  (trigger_status=confused, also applies paralyzed)
        to Chase C fires  (trigger_status=paralyzed)

Without applies_status on chase moves, the chain ends at step 1.

Usage:
    python manage.py fix_move_types_and_chase
    python manage.py fix_move_types_and_chase --dry-run
    python manage.py fix_move_types_and_chase --types-only
    python manage.py fix_move_types_and_chase --chase-only
"""
from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Type correction maps
# ---------------------------------------------------------------------------

# All current DB "Dragon"-type (15) moves are actually Fairy — full bulk swap.
# We retype every move currently assigned move_type 15 to 18 (Fairy).
# No name list needed; the entire Dragon bucket is Fairy.

# Dragon moves are currently stored as Rock (13). Same full-bucket swap.
# Rock (13) to Dragon (15).

# Rock moves are mixed into Ground (9). Identify by name.
_ROCK_MOVES_IN_GROUND: frozenset[str] = frozenset({
    "Accelerock", "Ancient Power", "Diamond Storm", "Head Smash",
    "Meteor Beam", "Mighty Cleave", "Power Gem", "Rock Blast",
    "Rock Polish", "Rock Slide", "Rock Throw", "Rock Tomb",
    "Rock Wrecker", "Rollout", "Salt Cure", "Salt Cure 2",
    "Smack Down", "Splintered Stormshards", "Stealth Rock",
    "Stone Axe", "Stone Edge",
})

# Dark moves mixed into Bug (12). Identify by name.
_DARK_MOVES_IN_BUG: frozenset[str] = frozenset({
    "Assurance", "Beat Up", "Black Hole Eclipse", "Black Hole Eclipse 2",
    "Brutal Swing", "Ceaseless Edge", "Ceaseless Edge 2",
    "Comeuppance", "Comeuppance 2",
    "Crunch", "Dark Pulse", "Dark Void", "Darkest Lariat",
    "Embargo", "Faint Attack", "Fake Tears", "False Surrender",
    "Fiery Wrath", "Fling", "Foul Play", "Hone Claws",
    "Hyperspace Fury", "Jaw Lock", "Knock Off", "Lash Out",
    "Memento", "Nasty Plot", "Night Daze", "Night Slash",
    "Obstruct", "Parting Shot", "Payback", "Power Trip",
    "Punishment", "Pursuit", "Quash", "Ruination", "Snatch",
    "Snarl", "Sucker Punch", "Switcheroo", "Taunt", "Thief",
    "Throat Chop", "Topsy-Turvy", "Torment", "Wicked Blow",
})

# Flying moves stored as Normal (1). Identify by name.
_FLYING_MOVES_IN_NORMAL: frozenset[str] = frozenset({
    "Acrobatics", "Aerial Ace", "Aeroblast", "Air Cutter", "Air Slash",
    "Beak Blast", "Bleakwind Storm", "Bounce", "Brave Bird", "Chatter",
    "Defog", "Dragon Ascent", "Drill Peck", "Dual Wingbeat",
    "Feather Dance", "Floaty Fall", "Fly", "Gust", "Hurricane",
    "Mirror Move", "Oblivion Wing", "Peck", "Pika Papow", "Pluck",
    "Roost", "Sandsear Storm", "Sky Attack", "Sky Drop", "Sky Uppercut",
    "Splishy Splash", "Supersonic Skystrike", "Tailwind", "Wing Attack",
})

# Steel moves stored as Normal (1). Identify by name.
_STEEL_MOVES_IN_NORMAL: frozenset[str] = frozenset({
    "Anchor Shot", "Autotomize", "Behemoth Bash", "Behemoth Blade",
    "Bullet Punch", "Doom Desire", "Flash Cannon", "Gear Grind",
    "Gyro Ball", "Heavy Slam", "Iron Defense", "Iron Head",
    "Iron Tail", "King's Shield", "Magnet Rise", "Metal Burst",
    "Metal Claw", "Metal Sound", "Meteor Mash", "Mirror Shot",
    "Shift Gear", "Smart Strike", "Steel Beam", "Steel Roller",
    "Steel Wing", "Zap Cannon",
})


# ---------------------------------------------------------------------------
# Chase-move status assignment
# Maps move_type name to StatusEffect PK to assign as applies_status
# These statuses propagate the team chain-trigger: when Chase A applies
# "confused", any ally with trigger_status=confused fires automatically.
# ---------------------------------------------------------------------------
# Status applied BY standard and chase moves of each type.
# Standard moves apply this to START a chain.
# Chase moves also apply this to CONTINUE a chain to a second ally.
_TYPE_APPLIES_STATUS: dict[str, int] = {
    "Fire":     1,   # burned      — heat lingers on contact
    "Water":    28,  # weakened    — water pressure saps strength
    "Electric": 4,   # paralyzed   — shock locks muscles
    "Grass":    11,  # seeded      — spores take root
    "Ice":      5,   # frozen      — sub-zero locks movement
    "Fighting": 9,   # flinched    — impact staggers target
    "Poison":   2,   # poisoned    — venom spreads through the hit
    "Ground":   21,  # immobile    — sand/mud anchors target
    "Rock":     9,   # flinched    — rock impacts stagger
    "Ghost":    7,   # confused    — spectral distortion clouds mind
    "Psychic":  7,   # confused    — psychic resonance
    "Bug":      23,  # blinded     — spores/silk blind target
    "Dark":     14,  # taunted     — dark aggression goads target
    "Dragon":   20,  # ignited     — draconic fire ignites
    "Normal":   9,   # flinched    — physical impact default
    "Flying":   31,  # airborne    — aerial strike lifts target
    "Steel":    28,  # weakened    — metal force drains strength
    "Fairy":    8,   # infatuated  — fairy charm enchants target
}

# Status that TRIGGERS each type's chase move.
# A chase fires when a friendly Pokemon inflicts this status on the enemy.
# Deliberately cross-wired so different type pairs chain naturally:
#   Fire standard (burned) -> Electric chase (trigger=burned) fires
#   Electric chase (applies paralyzed) -> Ground chase (trigger=paralyzed) fires
_TYPE_TRIGGER_STATUS: dict[str, int] = {
    "Fire":     1,   # triggers on burned     — heat ignites follow-up
    "Water":    28,  # triggers on weakened   — pressure compounds weakness
    "Electric": 1,   # triggers on burned     — electricity on burn is lethal
    "Grass":    11,  # triggers on seeded     — growth accelerates seeding
    "Ice":      4,   # triggers on paralyzed  — cold locks the paralysed
    "Fighting": 9,   # triggers on flinched   — press the staggered target
    "Poison":   7,   # triggers on confused   — toxin worsens confusion
    "Ground":   4,   # triggers on paralyzed  — earth pins the paralysed
    "Rock":     9,   # triggers on flinched   — rock buries the staggered
    "Ghost":    6,   # triggers on asleep     — haunts the sleeping target
    "Psychic":  7,   # triggers on confused   — amplifies mental distortion
    "Bug":      28,  # triggers on weakened   — swarms the weakened target
    "Dark":     14,  # triggers on taunted    — exploits the provoked state
    "Dragon":   20,  # triggers on ignited    — dragon fire fans the flames
    "Normal":   9,   # triggers on flinched   — follow-up on stagger
    "Flying":   31,  # triggers on airborne   — aerial finisher on launch
    "Steel":    2,   # triggers on poisoned   — corrodes the poisoned target
    "Fairy":    8,   # triggers on infatuated — enchantment deepens
}

# ---------------------------------------------------------------------------
# Chase-move applies_status (DIFFERENT from standard applies_status).
# Chase moves should ESCALATE or CROSS-WIRE to enable multi-type chains.
# If a chase applies the same status it triggers on, the chain dead-ends
# in a type self-loop.  Every entry here is deliberately different from
# the trigger status for that type.
#
# Design goals:
#   - Zero self-loops: trigger ≠ applies for every type
#   - Weakened Hub: multiple types funnel into weakened → Water/Bug fire
#   - Confused Hub: multiple types funnel into confused → Psychic/Poison fire
#   - Terminals for ultra-powerful effects (immobile, imprisoned, chaos)
#   - Thematic coherence with the type's identity
#
# Chain highlights:
#   Fire(burned)→Electric(paralyzed)→Ice(asleep)→Ghost(confused)→Poison(poisoned)→Steel(weakened)→...
#   Fire(chase:ignited)→Dragon(weakened)→Water/Bug→confused→Psychic/Poison
#   Grass(seeded→poisoned)→Steel(weakened)→Water/Bug→confused
#   Rock(flinched→airborne)→Flying(weakened)→Water/Bug→confused
# ---------------------------------------------------------------------------
_CHASE_APPLIES_STATUS: dict[str, str] = {
    # Was self-loop → now cross-wired:
    "Fire":     "ignited",    # burn escalates to deep ignition → Dragon chain
    "Water":    "confused",   # pressure/whirlpool disorients → Psychic/Poison chain
    "Grass":    "poisoned",   # toxic spores; Grass/Poison heritage → Steel chain
    "Ice":      "asleep",     # cold lullaby (replaces frozen dead-end) → Ghost chain
    "Fighting": "weakened",   # beaten down repeatedly → Water/Bug chain
    "Rock":     "airborne",   # Stone Edge launches target → Flying chain
    "Psychic":  "imprisoned", # mental seal; terminal (avoids Ghost↔Psychic infinite loop)
    "Bug":      "confused",   # swarm causes mental confusion → Psychic/Poison chain
    "Dark":     "confused",   # mind games disorient → Psychic/Poison chain
    "Dragon":   "weakened",   # overwhelming power saps strength → Water/Bug chain
    "Normal":   "weakened",   # generic beat-down → Water/Bug chain
    "Flying":   "weakened",   # aerial assault batters → Water/Bug chain
    "Fairy":    "chaos",      # enchantment → full mind control, terminal game-changer
    # Already correctly cross-wired (logic preserved):
    "Electric": "paralyzed",  # shock locks muscles → Ice/Ground chain
    "Poison":   "poisoned",   # venom spreads on hit → Steel chain
    "Ground":   "immobile",   # earth/mud anchors target → terminal CC
    "Ghost":    "confused",   # spectral haunting → Psychic/Poison chain
    "Steel":    "weakened",   # metal force drains strength → Water/Bug chain
}

# Keep old alias so Step 4 (standard moves) still works unchanged
_TYPE_CHASE_STATUS = _TYPE_APPLIES_STATUS


class Command(BaseCommand):
    help = (
        "Fix type misassignments in the move table and assign applies_status "
        "to all chase moves so team chain-triggers work correctly."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Preview changes without writing to the database.",
        )
        parser.add_argument(
            "--types-only",
            action="store_true",
            default=False,
            help="Only fix type misassignments; skip chase status update.",
        )
        parser.add_argument(
            "--chase-only",
            action="store_true",
            default=False,
            help="Only assign chase statuses; skip type corrections.",
        )
        parser.add_argument(
            "--reset-chase",
            action="store_true",
            default=False,
            help=(
                "Clear applies_status on ALL chase moves before reassigning. "
                "Required when re-running after statuses were already set."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from apps.effects.models import StatusEffect
        from apps.pokemon.models import Move, PokemonType

        dry_run: bool = options["dry_run"]
        types_only: bool = options["types_only"]
        chase_only: bool = options["chase_only"]
        reset_chase: bool = options["reset_chase"]

        self.stdout.write(self.style.MIGRATE_HEADING("=== fix_move_types_and_chase ==="))
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be written."))

        with transaction.atomic():

            # ------------------------------------------------------------------
            # Step 1 — Fix type misassignments
            # ------------------------------------------------------------------
            if not chase_only:
                self.stdout.write(self.style.MIGRATE_LABEL("Step 1: Correcting type misassignments …"))

                # Load type objects
                types: dict[str, PokemonType] = {
                    t.name: t for t in PokemonType.objects.all()
                }

                total_retyped = 0

                # 1a — Dragon (15) to Fairy (18): full bucket swap
                dragon_type = types.get("Dragon")
                fairy_type = types.get("Fairy")
                if dragon_type and fairy_type:
                    qs = Move.objects.filter(move_type=dragon_type)
                    count = qs.count()
                    if not dry_run:
                        qs.update(move_type=fairy_type)
                    self.stdout.write(
                        f"  {'[dry-run] Would retype' if dry_run else 'Retyped'} "
                        f"{count} Dragon-to-Fairy moves."
                    )
                    total_retyped += count

                # 1b — Rock (13) to Dragon (15): full bucket swap
                rock_type = types.get("Rock")
                dragon_type = types.get("Dragon")  # re-fetch after possible update
                if rock_type and dragon_type:
                    qs = Move.objects.filter(move_type=rock_type)
                    count = qs.count()
                    if not dry_run:
                        qs.update(move_type=dragon_type)
                    self.stdout.write(
                        f"  {'[dry-run] Would retype' if dry_run else 'Retyped'} "
                        f"{count} Rock-to-Dragon moves."
                    )
                    total_retyped += count

                # 1c — Ground subset to Rock (13)
                rock_type = types.get("Rock")
                ground_type = types.get("Ground")
                if ground_type and rock_type:
                    qs = Move.objects.filter(
                        move_type=ground_type,
                        name__in=_ROCK_MOVES_IN_GROUND,
                    )
                    count = qs.count()
                    if not dry_run:
                        qs.update(move_type=rock_type)
                    self.stdout.write(
                        f"  {'[dry-run] Would retype' if dry_run else 'Retyped'} "
                        f"{count} Ground-to-Rock moves."
                    )
                    total_retyped += count

                # 1d — Bug subset to Dark (16)
                bug_type = types.get("Bug")
                dark_type = types.get("Dark")
                if bug_type and dark_type:
                    qs = Move.objects.filter(
                        move_type=bug_type,
                        name__in=_DARK_MOVES_IN_BUG,
                    )
                    count = qs.count()
                    if not dry_run:
                        qs.update(move_type=dark_type)
                    self.stdout.write(
                        f"  {'[dry-run] Would retype' if dry_run else 'Retyped'} "
                        f"{count} Bug-to-Dark moves."
                    )
                    total_retyped += count

                # 1e — Normal subset to Flying (10)
                normal_type = types.get("Normal")
                flying_type = types.get("Flying")
                if normal_type and flying_type:
                    qs = Move.objects.filter(
                        move_type=normal_type,
                        name__in=_FLYING_MOVES_IN_NORMAL,
                    )
                    count = qs.count()
                    if not dry_run:
                        qs.update(move_type=flying_type)
                    self.stdout.write(
                        f"  {'[dry-run] Would retype' if dry_run else 'Retyped'} "
                        f"{count} Normal-to-Flying moves."
                    )
                    total_retyped += count

                # 1f — Normal subset to Steel (17)
                steel_type = types.get("Steel")
                if normal_type and steel_type:
                    qs = Move.objects.filter(
                        move_type=normal_type,
                        name__in=_STEEL_MOVES_IN_NORMAL,
                    )
                    count = qs.count()
                    if not dry_run:
                        qs.update(move_type=steel_type)
                    self.stdout.write(
                        f"  {'[dry-run] Would retype' if dry_run else 'Retyped'} "
                        f"{count} Normal-to-Steel moves."
                    )
                    total_retyped += count

                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Type corrections: {total_retyped} moves retyped total."
                    )
                )

            # ------------------------------------------------------------------
            # Step 2 — Assign applies_status to chase moves
            # ------------------------------------------------------------------
            if not types_only:
                self.stdout.write(
                    self.style.MIGRATE_LABEL(
                        "Step 2: Assigning applies_status to chase moves …"
                    )
                )

                from apps.effects.models import StatusEffect

                # Build lookup maps: PK→object (for Steps 3/4) and name→object (for Step 2)
                all_statuses = list(StatusEffect.objects.all())
                status_map: dict[int, Any] = {s.pk: s for s in all_statuses}
                status_by_name: dict[str, Any] = {s.name: s for s in all_statuses}

                # Optional reset: clear applies_status on all chase moves so we can
                # re-assign with the updated _CHASE_APPLIES_STATUS mapping.
                if reset_chase and not dry_run:
                    cleared = Move.objects.filter(slot_type="chase").update(
                        applies_status=None,
                        trigger_status=None,
                        combo_starter=False,
                        combo_trigger=False,
                    )
                    self.stdout.write(
                        self.style.WARNING(
                            f"  --reset-chase: cleared applies_status + trigger_status "
                            f"on {cleared} chase moves."
                        )
                    )
                elif reset_chase and dry_run:
                    cleared_count = Move.objects.filter(slot_type="chase").count()
                    self.stdout.write(
                        f"  [dry-run] --reset-chase would clear applies/trigger on "
                        f"{cleared_count} chase moves."
                    )

                # Load chase moves that need applies_status assigned
                chase_moves = list(
                    Move.objects.filter(
                        slot_type="chase",
                        applies_status__isnull=True,
                    ).select_related("move_type")
                )

                to_update: list[Move] = []
                skipped = 0

                for move in chase_moves:
                    type_name = move.move_type.name
                    status_name = _CHASE_APPLIES_STATUS.get(type_name)
                    if status_name is None:
                        logger.warning(
                            "No chase applies_status configured for type %s — skipping %s.",
                            type_name,
                            move.name,
                        )
                        skipped += 1
                        continue
                    status_obj = status_by_name.get(status_name)
                    if status_obj is None:
                        logger.warning(
                            "StatusEffect '%s' not found in DB — skipping %s (type %s).",
                            status_name,
                            move.name,
                            type_name,
                        )
                        skipped += 1
                        continue

                    move.applies_status = status_obj
                    move.combo_starter = True
                    to_update.append(move)

                if not dry_run:
                    Move.objects.bulk_update(
                        to_update,
                        ["applies_status", "combo_starter"],
                        batch_size=200,
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Updated {len(to_update)} chase moves with applies_status "
                            f"and combo_starter=True ({skipped} skipped — no type mapping)."
                        )
                    )
                else:
                    self.stdout.write(
                        f"  [dry-run] Would update {len(to_update)} chase moves "
                        f"({skipped} would be skipped)."
                    )

                # ------------------------------------------------------------------
                # Step 3 — Assign trigger_status to chase moves that lack it
                # ------------------------------------------------------------------
                self.stdout.write(
                    self.style.MIGRATE_LABEL(
                        "Step 3: Assigning trigger_status to chase moves …"
                    )
                )

                chase_no_trigger = list(
                    Move.objects.filter(
                        slot_type="chase",
                        trigger_status__isnull=True,
                    ).select_related("move_type")
                )

                trigger_updates: list[Move] = []
                trigger_skipped = 0

                for move in chase_no_trigger:
                    type_name = move.move_type.name
                    status_pk = _TYPE_TRIGGER_STATUS.get(type_name)
                    if status_pk is None or status_pk not in status_map:
                        trigger_skipped += 1
                        continue
                    move.trigger_status = status_map[status_pk]
                    move.combo_trigger = True
                    trigger_updates.append(move)

                if not dry_run:
                    Move.objects.bulk_update(
                        trigger_updates,
                        ["trigger_status", "combo_trigger"],
                        batch_size=200,
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Set trigger_status + combo_trigger=True on "
                            f"{len(trigger_updates)} chase moves ({trigger_skipped} skipped)."
                        )
                    )
                else:
                    self.stdout.write(
                        f"  [dry-run] Would set trigger_status on {len(trigger_updates)} chase moves."
                    )

                # ------------------------------------------------------------------
                # Step 4 — Assign applies_status to standard moves that lack it
                # ------------------------------------------------------------------
                self.stdout.write(
                    self.style.MIGRATE_LABEL(
                        "Step 4: Assigning applies_status to standard moves …"
                    )
                )

                std_no_status = list(
                    Move.objects.filter(
                        slot_type="standard",
                        applies_status__isnull=True,
                    ).select_related("move_type")
                )

                std_updates: list[Move] = []
                std_skipped = 0

                for move in std_no_status:
                    type_name = move.move_type.name
                    status_pk = _TYPE_APPLIES_STATUS.get(type_name)
                    if status_pk is None or status_pk not in status_map:
                        std_skipped += 1
                        continue
                    move.applies_status = status_map[status_pk]
                    move.combo_starter = True
                    std_updates.append(move)

                if not dry_run:
                    Move.objects.bulk_update(
                        std_updates,
                        ["applies_status", "combo_starter"],
                        batch_size=200,
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Set applies_status + combo_starter=True on "
                            f"{len(std_updates)} standard moves ({std_skipped} skipped)."
                        )
                    )
                else:
                    self.stdout.write(
                        f"  [dry-run] Would set applies_status on {len(std_updates)} standard moves."
                    )

                # ------------------------------------------------------------------
                # Verification summary
                # ------------------------------------------------------------------
                if not dry_run:
                    for slot, field in [
                        ("standard", "applies_status"),
                        ("chase", "applies_status"),
                        ("chase", "trigger_status"),
                    ]:
                        missing = Move.objects.filter(
                            slot_type=slot,
                            **{f"{field}__isnull": True},
                        ).count()
                        label = f"{slot}.{field}"
                        if missing:
                            self.stdout.write(
                                self.style.WARNING(f"  {label}: {missing} still missing.")
                            )
                        else:
                            self.stdout.write(
                                self.style.SUCCESS(f"  {label}: all covered.")
                            )

            if dry_run:
                transaction.set_rollback(True)

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run complete — database unchanged."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "fix_move_types_and_chase complete. "
                    "Re-run apply_gen1_roles --clear to rebuild pools with correct types."
                )
            )
