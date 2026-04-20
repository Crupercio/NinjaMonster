"""
backfill_chakra_cost — assign chakra_cost to all mystery-slot moves.

Tier rules (based on move power):
  20  Light    — power 0 (status-only / OHKO gimmicks)
  35  Standard — power 1–89
  50  Heavy    — power 90–129
  80  Forbidden— power 130+

Run order:
  python manage.py backfill_chakra_cost           # apply tiers
  python manage.py backfill_chakra_cost --dry-run  # preview only
  python manage.py backfill_chakra_cost --reset    # set all mystery costs to 0 first, then re-apply
"""
import logging

from django.core.management.base import BaseCommand

from apps.pokemon.models import Move, MoveSlotType

logger = logging.getLogger(__name__)


def _tier_for_power(power: int) -> int:
    if power == 0:
        return 20   # status-only / utility
    if power < 90:
        return 35   # standard damage
    if power < 130:
        return 50   # heavy
    return 80       # forbidden


class Command(BaseCommand):
    help = "Assign chakra_cost tiers to all mystery-slot moves."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print changes without saving.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Zero out all mystery move chakra costs before re-applying tiers.",
        )

    def handle(self, *args, **options) -> None:
        dry_run: bool = options["dry_run"]
        reset: bool = options["reset"]

        mystery_moves = list(Move.objects.filter(slot_type=MoveSlotType.MYSTERY))
        self.stdout.write(f"Found {len(mystery_moves)} mystery moves.")

        if reset and not dry_run:
            Move.objects.filter(slot_type=MoveSlotType.MYSTERY).update(chakra_cost=0)
            self.stdout.write("Reset all mystery chakra costs to 0.")

        tier_counts: dict[int, int] = {20: 0, 35: 0, 50: 0, 80: 0}
        to_update: list[Move] = []

        for move in mystery_moves:
            tier = _tier_for_power(move.power)
            if move.chakra_cost != tier:
                tier_counts[tier] += 1
                if dry_run:
                    self.stdout.write(
                        f"  [DRY] {move.name!r:40s}  power={move.power:>4}  "
                        f"cost: {move.chakra_cost} -> {tier}"
                    )
                else:
                    move.chakra_cost = tier
                    to_update.append(move)

        if not dry_run and to_update:
            Move.objects.bulk_update(to_update, fields=["chakra_cost"])
            self.stdout.write(self.style.SUCCESS(
                f"Updated {len(to_update)} moves: "
                f"20-cost={tier_counts[20]}, "
                f"35-cost={tier_counts[35]}, "
                f"50-cost={tier_counts[50]}, "
                f"80-cost={tier_counts[80]}"
            ))
        elif dry_run:
            self.stdout.write(
                f"[DRY RUN] Would update: "
                f"20-cost={tier_counts[20]}, "
                f"35-cost={tier_counts[35]}, "
                f"50-cost={tier_counts[50]}, "
                f"80-cost={tier_counts[80]}"
            )
        else:
            self.stdout.write("All mystery moves already have correct chakra costs. Nothing to do.")
