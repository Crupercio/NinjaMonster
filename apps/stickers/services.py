"""
Sticker business logic: StickerService and TradeService.

Implements all award, upgrade, pack-opening, dust conversion, crafting,
and atomic trade mechanics.
"""
import logging
import random
from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, F

from apps.pokemon.models import Pokemon
from apps.users.services import deduct_ryo

from .models import (
    BADGE_CRAFT_REQUIREMENTS,
    CRAFT_COSTS,
    DISMANTLE_VALUES,
    DUST_VALUES,
    GEN_PACK_GEN_NUMBER,
    PAGE_REWARDS,
    REGION_LABELS,
    REGION_RANGES,
    AlbumCompletionReward,
    AlbumPage,
    AlbumRewardType,
    Badge,
    BadgeTier,
    OwnedBadge,
    RegionalAlbumPage,
    Sticker,
    StickerAlbum,
    PackType,
    StickerPack,
    StickerRarity,
    StickerVariant,
    TradeHistory,
    TradeOffer,
)

User = get_user_model()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pack rarity distribution weights
# ---------------------------------------------------------------------------
# Slots 1-3: common / uncommon
_COMMON_POOL_WEIGHTS = {
    StickerRarity.COMMON: 70,
    StickerRarity.UNCOMMON: 30,
}
# Slot 4: guaranteed rare or above
_GUARANTEED_RARE_WEIGHTS = {
    StickerRarity.RARE: 60,
    StickerRarity.EPIC: 25,
    StickerRarity.HOLOGRAPHIC: 10,
    StickerRarity.FULL_ART: 4,
    StickerRarity.SECRET_RARE: 1,
}
# Slot 5: any rarity
_ANY_RARITY_WEIGHTS = {
    StickerRarity.COMMON: 50,
    StickerRarity.UNCOMMON: 25,
    StickerRarity.RARE: 15,
    StickerRarity.EPIC: 6,
    StickerRarity.HOLOGRAPHIC: 3,
    StickerRarity.FULL_ART: 0.7,
    StickerRarity.SECRET_RARE: 0.3,
}

# Variant weights for random assignment
_VARIANT_WEIGHTS = {
    StickerVariant.BASE: 50,
    StickerVariant.SHINY: 25,
    StickerVariant.BATTLE_SCENE: 12,
    StickerVariant.CHIBI: 8,
    StickerVariant.MANGA_PANEL: 4,
    StickerVariant.FULL_ILLUSTRATION: 1,
}

# Level milestones that upgrade sticker rarity
_LEVEL_RARITY_UPGRADES: dict[int, str] = {
    25: StickerRarity.UNCOMMON,
    50: StickerRarity.RARE,
    75: StickerRarity.EPIC,
    100: StickerRarity.HOLOGRAPHIC,
}

# Secret rare drop chance when catching at 1 HP
_SECRET_RARE_HP_CHANCE = 0.03  # 3%

# Minimum combo chain length for full_art award
_FULL_ART_MIN_CHAIN = 5

# Battles won required to earn a sticker pack
_BATTLES_PER_PACK = 10

# Pity thresholds — packs opened without that rarity before a guaranteed pull
_PITY_HOLOGRAPHIC = 10
_PITY_FULL_ART = 50
_PITY_SECRET_RARE = 200

# ── Shop pricing — change here to affect the whole feature ──────────────────
PACK_PRICE_RYO: int = 500  # cost of one sticker pack
# ────────────────────────────────────────────────────────────────────────────

# ── Album completion (GDD §20.13) ────────────────────────────────────────────
# 7 rarities × 6 non-ANIME variants = 42 valid (rarity, variant) slots per Pokemon.
# ANIME variant is excluded — it is only available on SECRET_RARE and is a
# cosmetic bonus that does not count toward completion.
_COMPLETION_VARIANTS: list[str] = [
    StickerVariant.BASE,
    StickerVariant.SHINY,
    StickerVariant.BATTLE_SCENE,
    StickerVariant.CHIBI,
    StickerVariant.MANGA_PANEL,
    StickerVariant.FULL_ILLUSTRATION,
]
_COMPLETION_RARITIES: list[str] = list(StickerRarity.values)  # all 7

POKEMON_COMPLETION_SLOTS: int = len(_COMPLETION_RARITIES) * len(_COMPLETION_VARIANTS)  # 42

# Rewards for completing all 42 slots of a single Pokemon
POKEMON_COMPLETE_DUST: int = 500
POKEMON_COMPLETE_RYO: int = 2_000

# Legendary reward for completing every Pokemon in the Pokedex
FULL_DEX_DUST: int = 5_000
FULL_DEX_RYO: int = 10_000
FULL_DEX_PACKS: int = 3
# ─────────────────────────────────────────────────────────────────────────────


def _weighted_choice(weights: dict[str, float]) -> str:
    """Return a random key from a dict of {value: weight} using weighted sampling."""
    population = list(weights.keys())
    wt = list(weights.values())
    return random.choices(population, weights=wt, k=1)[0]


def _random_variant() -> str:
    """Return a randomly weighted sticker variant."""
    return _weighted_choice(_VARIANT_WEIGHTS)


def _get_or_create_album(user: User) -> StickerAlbum:
    album, _ = StickerAlbum.objects.get_or_create(owner=user)
    return album


class StickerService:
    """
    Handles all sticker award, upgrade, pack-opening, dust, and crafting logic.
    """

    @transaction.atomic
    def award_on_catch(
        self, player: User, pokemon: Pokemon, hp_remaining: int
    ) -> Sticker:
        """
        Award a sticker when a player catches a Pokemon.

        If the Pokemon was caught at exactly 1 HP, there is a 3% chance of
        awarding a secret_rare sticker instead of common.
        """
        _get_or_create_album(player)

        rarity = StickerRarity.COMMON
        if hp_remaining == 1 and random.random() < _SECRET_RARE_HP_CHANCE:
            rarity = StickerRarity.SECRET_RARE
            logger.info(
                "Secret rare sticker awarded to %s for catching %s at 1 HP!",
                player,
                pokemon.name,
            )

        variant = _random_variant()
        sticker = Sticker.objects.create(
            pokemon=pokemon,
            owner=player,
            rarity=rarity,
            variant=variant,
            awarded_from="catch",
        )
        logger.info("Awarded %s sticker to %s for catching %s", rarity, player, pokemon.name)
        return sticker

    @transaction.atomic
    def award_on_level_up(
        self, player: User, pokemon: Pokemon, new_level: int
    ) -> Sticker | None:
        """
        Award or upgrade a sticker when a caught Pokemon reaches a milestone level.

        Milestones: 25 → uncommon, 50 → rare, 75 → epic, 100 → holographic.
        Returns the new sticker or None if no milestone was hit.
        """
        rarity = _LEVEL_RARITY_UPGRADES.get(new_level)
        if rarity is None:
            return None

        variant = _random_variant()
        sticker = Sticker.objects.create(
            pokemon=pokemon,
            owner=player,
            rarity=rarity,
            variant=variant,
            awarded_from="level_up",
        )
        logger.info(
            "Awarded %s sticker to %s (%s reached level %d)",
            rarity,
            player,
            pokemon.name,
            new_level,
        )
        return sticker

    @transaction.atomic
    def award_on_combo_win(
        self, player: User, chain_length: int, pokemon: Pokemon | None = None
    ) -> Sticker | None:
        """
        Award a full_art sticker when winning with a combo chain >= 5.

        Returns the sticker or None if the chain was too short.
        """
        if chain_length < _FULL_ART_MIN_CHAIN:
            return None

        if pokemon is None:
            pokemon = Pokemon.objects.order_by("?").first()
        if pokemon is None:
            return None

        variant = _random_variant()
        sticker = Sticker.objects.create(
            pokemon=pokemon,
            owner=player,
            rarity=StickerRarity.FULL_ART,
            variant=variant,
            awarded_from="combo_win",
        )
        logger.info(
            "Awarded full_art sticker to %s for combo chain of %d",
            player,
            chain_length,
        )
        return sticker

    @transaction.atomic
    def buy_pack(self, player: User, pack_type: str = PackType.STANDARD) -> StickerPack:
        """
        Spend PACK_PRICE_RYO to purchase and immediately receive a sticker pack.

        pack_type may be any PackType value (standard, bundle, gen1–gen8).
        Gen packs cost the same as standard packs but draw only from that generation.
        Raises ValueError if the player cannot afford the pack or pack_type is invalid.
        Returns the new (unopened) StickerPack.
        """
        if pack_type not in PackType.values:
            raise ValueError(f"Invalid pack type: {pack_type}")
        deduct_ryo(player, PACK_PRICE_RYO)
        pack = StickerPack.objects.create(owner=player, pack_type=pack_type)
        logger.info(
            "Player %s bought a %s for %d Ryo",
            player,
            pack_type,
            PACK_PRICE_RYO,
        )
        return pack

    @transaction.atomic
    def grant_pack_if_eligible(self, player: User) -> StickerPack | None:
        """
        Grant a sticker pack if the player's win count is a multiple of 10.

        Returns the new StickerPack or None if not eligible.
        """
        if player.battles_won > 0 and player.battles_won % _BATTLES_PER_PACK == 0:
            pack = StickerPack.objects.create(owner=player)
            logger.info("Granted sticker pack to %s (wins: %d)", player, player.battles_won)
            return pack
        return None

    # Bundle pack rarity weights — boosted rare+ odds compared to standard
    _BUNDLE_COMMON_POOL_WEIGHTS = [
        (StickerRarity.COMMON, 60),
        (StickerRarity.UNCOMMON, 40),
    ]
    _BUNDLE_GUARANTEED_RARE_WEIGHTS = [
        (StickerRarity.RARE, 55),
        (StickerRarity.EPIC, 25),
        (StickerRarity.HOLOGRAPHIC, 15),
        (StickerRarity.FULL_ART, 4),
        (StickerRarity.SECRET_RARE, 1),
    ]
    _BUNDLE_ANY_RARITY_WEIGHTS = [
        (StickerRarity.COMMON, 35),
        (StickerRarity.UNCOMMON, 30),
        (StickerRarity.RARE, 20),
        (StickerRarity.EPIC, 10),
        (StickerRarity.HOLOGRAPHIC, 4),
        (StickerRarity.FULL_ART, 1),
    ]

    @transaction.atomic
    def open_pack(self, player: User, pack: StickerPack) -> list[Sticker]:
        """
        Open a sticker pack and reveal stickers.

        Standard (5 stickers):
          Slots 1-3: common or uncommon (weighted)
          Slot 4: guaranteed rare or above (may be overridden by pity)
          Slot 5: any rarity (full weighted table)

        Bundle (10 stickers):
          Slots 1-5: common or uncommon (boosted weights)
          Slots 6-9: guaranteed rare or above (boosted weights, each slot independent)
          Slot 10: any rarity (boosted table)

        Pity system applies to both types (slot 4 for standard, slot 6 for bundle).

        Returns the list of Sticker instances.
        """
        if pack.owner != player:
            raise ValueError("This pack does not belong to the player")
        if pack.opened:
            raise ValueError("This pack has already been opened")

        is_bundle = pack.pack_type == PackType.BUNDLE

        # Lock player row so pity counters update atomically across concurrent opens
        player = User.objects.select_for_update().get(pk=player.pk)

        # Build pokemon pool — gen packs restrict to that generation's pokemon
        gen_number = GEN_PACK_GEN_NUMBER.get(pack.pack_type)
        if gen_number is not None:
            all_pokemon = list(
                Pokemon.objects.filter(generation__number=gen_number)
            )
            if not all_pokemon:
                # Fallback to full pool if gen not yet seeded
                all_pokemon = list(Pokemon.objects.all())
        else:
            all_pokemon = list(Pokemon.objects.all())
        if not all_pokemon:
            raise ValueError("No Pokemon in database to generate stickers from")

        # Determine pity override for the guaranteed-rare slot
        pity_override: str | None = None
        if player.pity_secret_rare >= _PITY_SECRET_RARE:
            pity_override = StickerRarity.SECRET_RARE
        elif player.pity_full_art >= _PITY_FULL_ART:
            pity_override = StickerRarity.FULL_ART
        elif player.pity_holographic >= _PITY_HOLOGRAPHIC:
            pity_override = StickerRarity.HOLOGRAPHIC

        stickers: list[Sticker] = []
        common_weights = self._BUNDLE_COMMON_POOL_WEIGHTS if is_bundle else _COMMON_POOL_WEIGHTS
        rare_weights = self._BUNDLE_GUARANTEED_RARE_WEIGHTS if is_bundle else _GUARANTEED_RARE_WEIGHTS
        any_weights = self._BUNDLE_ANY_RARITY_WEIGHTS if is_bundle else _ANY_RARITY_WEIGHTS
        common_slots = 5 if is_bundle else 3
        rare_slots = 4 if is_bundle else 1  # slots 6-9 for bundle, slot 4 for standard

        # Common/uncommon slots
        for _ in range(common_slots):
            rarity = _weighted_choice(common_weights)
            stickers.append(self._create_random_sticker(player, all_pokemon, rarity, "pack"))

        # First guaranteed-rare slot — apply pity
        rarity = pity_override if pity_override is not None else _weighted_choice(rare_weights)
        stickers.append(self._create_random_sticker(player, all_pokemon, rarity, "pack"))

        # Extra guaranteed-rare slots for bundle (no pity applied to extras)
        for _ in range(rare_slots - 1):
            rarity = _weighted_choice(rare_weights)
            stickers.append(self._create_random_sticker(player, all_pokemon, rarity, "pack"))

        # Final any-rarity slot
        rarity = _weighted_choice(any_weights)
        stickers.append(self._create_random_sticker(player, all_pokemon, rarity, "pack"))

        pack.stickers.add(*stickers)
        pack.opened = True
        pack.opened_at = datetime.now(tz=timezone.utc)
        pack.save(update_fields=["opened", "opened_at"])

        # Update pity counters — higher rarities also satisfy lower thresholds
        rarities_obtained = {s.rarity for s in stickers}
        got_secret_rare = StickerRarity.SECRET_RARE in rarities_obtained
        got_full_art = got_secret_rare or StickerRarity.FULL_ART in rarities_obtained
        got_holographic = got_full_art or StickerRarity.HOLOGRAPHIC in rarities_obtained

        player.pity_holographic = 0 if got_holographic else player.pity_holographic + 1
        player.pity_full_art = 0 if got_full_art else player.pity_full_art + 1
        player.pity_secret_rare = 0 if got_secret_rare else player.pity_secret_rare + 1
        player.save(update_fields=["pity_holographic", "pity_full_art", "pity_secret_rare"])

        if pity_override is not None:
            logger.info(
                "Pity trigger: %s guaranteed %s in pack (counters reset)",
                player,
                pity_override,
            )

        logger.info("Player %s opened a sticker pack — got %d stickers", player, len(stickers))

        from apps.quests.services import QuestService
        QuestService().on_pack_opened(player)

        # Check album completion for every unique Pokemon in this pack
        pokemon_ids = {s.pokemon_id for s in stickers}
        self.maybe_award_completion_rewards(player, pokemon_ids)

        return stickers

    @transaction.atomic
    def convert_duplicate(self, player: User, sticker: Sticker) -> int:
        """
        Convert a duplicate sticker to sticker dust.

        A sticker cannot be converted if the player has only one copy of that
        (pokemon, rarity, variant) combination.

        Returns the dust amount gained.
        """
        if sticker.owner != player:
            raise ValueError("This sticker does not belong to the player")
        if sticker.is_trading:
            raise ValueError("Cannot convert a sticker that is currently in a trade")
        if sticker.is_album_placed:
            raise ValueError("Cannot convert a sticker that is placed in your album")

        # Count copies the player owns of this exact combination
        copy_count = Sticker.objects.filter(
            owner=player,
            pokemon=sticker.pokemon,
            rarity=sticker.rarity,
            variant=sticker.variant,
        ).count()

        if copy_count <= 1:
            raise ValueError(
                f"Cannot convert your only copy of {sticker.pokemon.name} "
                f"[{sticker.rarity}] {sticker.variant}"
            )

        dust = DUST_VALUES.get(sticker.rarity, 5)
        sticker.delete()

        player.sticker_dust += dust
        player.save(update_fields=["sticker_dust"])

        logger.info("Player %s converted a sticker for %d dust", player, dust)
        return dust

    @transaction.atomic
    def dismantle_sticker(self, player: User, sticker_id: int) -> int:
        """
        Dismantle any owned sticker for dust — no duplicate requirement.

        Dust values: Common 5 · Uncommon 10 · Rare 25 · Epic 60 ·
                     Holographic 120 · Full Art 200 · Secret Rare 300.

        Returns the dust amount awarded.
        Raises ValueError if the sticker is not owned by player or is in a trade.
        """
        sticker = Sticker.objects.select_for_update().filter(
            pk=sticker_id, owner=player
        ).first()
        if sticker is None:
            raise ValueError("Sticker not found or does not belong to you")
        if sticker.is_trading:
            raise ValueError("Cannot dismantle a sticker that is listed for trade")
        if sticker.is_favorite:
            raise ValueError("Cannot dismantle a favourited sticker — unfavourite it first")
        if sticker.is_album_placed:
            raise ValueError("Cannot dismantle a sticker that is placed in your album")

        dust = DISMANTLE_VALUES.get(sticker.rarity, 5)
        sticker.delete()

        player.sticker_dust += dust
        player.save(update_fields=["sticker_dust"])

        logger.info(
            "Player %s dismantled sticker #%d (%s %s) for %d dust",
            player,
            sticker_id,
            sticker.rarity,
            sticker.variant,
            dust,
        )
        return dust

    @transaction.atomic
    def craft_sticker(
        self,
        player: User,
        pokemon: Pokemon,
        variant: str,
        rarity: str,
    ) -> Sticker:
        """
        Spend sticker dust to craft a specific sticker variant.

        Raises ValueError if insufficient dust or invalid rarity/variant.
        """
        cost = CRAFT_COSTS.get(rarity)
        if cost is None:
            raise ValueError(f"Unknown rarity: {rarity}")
        if variant not in StickerVariant.values:
            raise ValueError(f"Unknown variant: {variant}")
        if player.sticker_dust < cost:
            raise ValueError(
                f"Insufficient dust: need {cost}, have {player.sticker_dust}"
            )

        player.sticker_dust -= cost
        player.save(update_fields=["sticker_dust"])

        sticker = Sticker.objects.create(
            pokemon=pokemon,
            owner=player,
            rarity=rarity,
            variant=variant,
            awarded_from="craft",
        )
        logger.info(
            "Player %s crafted %s [%s] %s for %d dust",
            player,
            pokemon.name,
            rarity,
            variant,
            cost,
        )
        self.maybe_award_completion_rewards(player, {pokemon.pk})
        return sticker

    def get_album(self, user: User) -> dict:
        """
        Return album stats for display.

        {
          "total_stickers": int,
          "unique_pokemon": int,
          "rarity_breakdown": {rarity: count},
          "completion_percentage": float,
          "by_type": {type_name: {"total": int, "owned": int, "completion": float}},
          "showcase": [Sticker],
        }
        """
        _get_or_create_album(user)
        owned = Sticker.objects.filter(owner=user).select_related("pokemon__primary_type")
        total_pokemon = Pokemon.objects.count()

        rarity_breakdown: dict[str, int] = {}
        for rarity in StickerRarity.values:
            rarity_breakdown[rarity] = owned.filter(rarity=rarity).count()

        unique_pokemon = owned.values("pokemon").distinct().count()
        completion = round(unique_pokemon / total_pokemon * 100, 1) if total_pokemon else 0.0

        # By-type breakdown
        from apps.pokemon.models import PokemonType

        by_type: dict[str, dict] = {}
        for ptype in PokemonType.objects.all():
            type_pokemon_count = (
                Pokemon.objects.filter(
                    primary_type=ptype
                )
                | Pokemon.objects.filter(secondary_type=ptype)
            ).distinct().count()
            owned_of_type = owned.filter(
                pokemon__primary_type=ptype
            ).values("pokemon").distinct().count()
            by_type[ptype.name] = {
                "total": type_pokemon_count,
                "owned": owned_of_type,
                "completion": round(owned_of_type / type_pokemon_count * 100, 1) if type_pokemon_count else 0.0,
            }

        # Showcase stickers
        album = StickerAlbum.objects.filter(owner=user).first()
        showcase = list(album.showcase_stickers.all()) if album else []

        return {
            "total_stickers": owned.count(),
            "unique_pokemon": unique_pokemon,
            "rarity_breakdown": rarity_breakdown,
            "completion_percentage": completion,
            "by_type": by_type,
            "showcase": showcase,
        }

    # ------------------------------------------------------------------
    # Album completion rewards (GDD §20.13)
    # ------------------------------------------------------------------

    def check_pokemon_completion(self, user: User, pokemon: Pokemon) -> bool:
        """
        Return True if the user owns at least one sticker for every valid
        (rarity, variant) combination for the given Pokemon.

        Valid combinations: all 7 rarities × 6 non-ANIME variants = 42 slots.
        """
        owned_slots = set(
            Sticker.objects.filter(
                owner=user,
                pokemon=pokemon,
                variant__in=_COMPLETION_VARIANTS,
            ).values_list("rarity", "variant").distinct()
        )
        required_slots = {
            (rarity, variant)
            for rarity in _COMPLETION_RARITIES
            for variant in _COMPLETION_VARIANTS
        }
        return required_slots.issubset(owned_slots)

    def maybe_award_completion_rewards(
        self, user: User, pokemon_ids: set[int]
    ) -> list[dict]:
        """
        Check each pokemon_id for newly achieved completion and auto-award
        the appropriate reward if not already claimed.

        After checking individual Pokemon, also checks full dex completion.

        Returns a list of award summary dicts (one per reward granted):
          {"type": "pokemon", "pokemon": <Pokemon>, "dust": 500, "ryo": 2000}
          {"type": "full_dex", "dust": 5000, "ryo": 10000, "packs": 3}
        """
        summaries: list[dict] = []

        for pokemon_id in pokemon_ids:
            try:
                pokemon = Pokemon.objects.get(pk=pokemon_id)
            except Pokemon.DoesNotExist:
                continue

            if not self.check_pokemon_completion(user, pokemon):
                continue

            # Guard: already awarded?
            _, created = AlbumCompletionReward.objects.get_or_create(
                user=user,
                reward_type=AlbumRewardType.POKEMON_COMPLETE,
                pokemon=pokemon,
                defaults={
                    "dust_awarded": POKEMON_COMPLETE_DUST,
                    "ryo_awarded": POKEMON_COMPLETE_RYO,
                    "packs_awarded": 0,
                },
            )
            if not created:
                continue  # already claimed previously

            # Award
            user.sticker_dust += POKEMON_COMPLETE_DUST
            user.ryo += POKEMON_COMPLETE_RYO
            user.save(update_fields=["sticker_dust", "ryo"])

            summaries.append({
                "type": "pokemon",
                "pokemon": pokemon,
                "dust": POKEMON_COMPLETE_DUST,
                "ryo": POKEMON_COMPLETE_RYO,
            })
            logger.info(
                "Pokemon completion reward: user=%s pokemon=%s dust=%d ryo=%d",
                user,
                pokemon.name,
                POKEMON_COMPLETE_DUST,
                POKEMON_COMPLETE_RYO,
            )

        # Check full dex only if at least one new pokemon reward was just granted
        if summaries and self._check_full_dex_completion(user):
            _, created = AlbumCompletionReward.objects.get_or_create(
                user=user,
                reward_type=AlbumRewardType.FULL_DEX,
                pokemon=None,
                defaults={
                    "dust_awarded": FULL_DEX_DUST,
                    "ryo_awarded": FULL_DEX_RYO,
                    "packs_awarded": FULL_DEX_PACKS,
                },
            )
            if created:
                user.sticker_dust += FULL_DEX_DUST
                user.ryo += FULL_DEX_RYO
                user.save(update_fields=["sticker_dust", "ryo"])
                for _ in range(FULL_DEX_PACKS):
                    StickerPack.objects.create(owner=user)
                summaries.append({
                    "type": "full_dex",
                    "dust": FULL_DEX_DUST,
                    "ryo": FULL_DEX_RYO,
                    "packs": FULL_DEX_PACKS,
                })
                logger.info(
                    "Full dex completion reward: user=%s dust=%d ryo=%d packs=%d",
                    user,
                    FULL_DEX_DUST,
                    FULL_DEX_RYO,
                    FULL_DEX_PACKS,
                )

        return summaries

    def _check_full_dex_completion(self, user: User) -> bool:
        """Return True if every Pokemon in the DB is individually complete for user."""
        all_pokemon = list(Pokemon.objects.only("pk"))
        if not all_pokemon:
            return False
        completed_ids = set(
            AlbumCompletionReward.objects.filter(
                user=user,
                reward_type=AlbumRewardType.POKEMON_COMPLETE,
            ).values_list("pokemon_id", flat=True)
        )
        return all(p.pk in completed_ids for p in all_pokemon)

    def get_completion_rewards_for_album(self, user: User) -> dict:
        """
        Return album completion context for the album page:
          {
            "completed_pokemon_ids": set[int],
            "full_dex_claimed": bool,
            "total_completions": int,
          }
        """
        qs = AlbumCompletionReward.objects.filter(user=user)
        completed_ids = set(
            qs.filter(
                reward_type=AlbumRewardType.POKEMON_COMPLETE
            ).values_list("pokemon_id", flat=True)
        )
        full_dex_claimed = qs.filter(reward_type=AlbumRewardType.FULL_DEX).exists()
        return {
            "completed_pokemon_ids": completed_ids,
            "full_dex_claimed": full_dex_claimed,
            "total_completions": len(completed_ids),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _create_random_sticker(
        self,
        player: User,
        pokemon_pool: list[Pokemon],
        rarity: str,
        source: str,
    ) -> Sticker:
        """Create a sticker for a random Pokemon from the pool."""
        pokemon = random.choice(pokemon_pool)
        variant = _random_variant()
        return Sticker.objects.create(
            pokemon=pokemon,
            owner=player,
            rarity=rarity,
            variant=variant,
            awarded_from=source,
        )


class TradeService:
    """Handles peer-to-peer sticker trading with atomic ownership swaps."""

    @transaction.atomic
    def create_trade_offer(
        self,
        sender: User,
        sticker: Sticker,
        requested_sticker: Sticker | None = None,
        requested_pokemon: Pokemon | None = None,
        looking_for_note: str = "",
        offered_to: User | None = None,
    ) -> TradeOffer:
        """
        Create a trade offer listing a sticker.

        Validates:
        - Sender owns the sticker
        - Sticker not already in a trade
        - Sender has more than one copy (cannot trade their last copy)
        """
        if sticker.owner != sender:
            raise ValueError("You do not own this sticker")
        if sticker.is_trading:
            raise ValueError("This sticker is already listed for trade")
        if sticker.is_album_placed:
            raise ValueError("Cannot trade a sticker that is placed in your album")

        # Cannot trade the only copy
        copy_count = Sticker.objects.filter(
            owner=sender,
            pokemon=sticker.pokemon,
            rarity=sticker.rarity,
            variant=sticker.variant,
        ).count()
        if copy_count <= 1:
            raise ValueError(
                "You cannot trade your only copy of "
                f"{sticker.pokemon.name} [{sticker.rarity}] {sticker.variant}"
            )

        sticker.is_trading = True
        sticker.save(update_fields=["is_trading"])

        offer = TradeOffer.objects.create(
            offered_sticker=sticker,
            requested_sticker=requested_sticker,
            requested_pokemon=requested_pokemon,
            looking_for_note=looking_for_note,
            offered_by=sender,
            offered_to=offered_to,
            status=TradeOffer.Status.PENDING,
        )
        logger.info("Trade offer #%d created by %s", offer.pk, sender)
        return offer

    @transaction.atomic
    def accept_trade(
        self, receiver: User, offer: TradeOffer, accepting_sticker: Sticker
    ) -> tuple[Sticker, Sticker]:
        """
        Atomically swap ownership of two stickers to complete a trade.

        Uses select_for_update() to prevent race conditions when two users
        try to accept the same offer simultaneously.

        Returns (sticker_receiver_now_owns, sticker_sender_now_owns).
        """
        # Lock both stickers and the offer for atomic update
        offer = TradeOffer.objects.select_for_update().get(pk=offer.pk)
        offered_sticker = Sticker.objects.select_for_update().get(pk=offer.offered_sticker_id)
        accepting_sticker = Sticker.objects.select_for_update().get(pk=accepting_sticker.pk)

        if offer.status != TradeOffer.Status.PENDING:
            raise ValueError(f"This trade offer is no longer pending (status: {offer.status})")
        if accepting_sticker.owner != receiver:
            raise ValueError("You do not own the sticker you are offering in exchange")
        if accepting_sticker.is_trading:
            raise ValueError("The sticker you are offering is already in another trade")

        # Cannot trade the only copy
        copy_count = Sticker.objects.filter(
            owner=receiver,
            pokemon=accepting_sticker.pokemon,
            rarity=accepting_sticker.rarity,
            variant=accepting_sticker.variant,
        ).count()
        if copy_count <= 1:
            raise ValueError("You cannot trade your only copy of this sticker")

        # Swap ownership
        original_sender = offer.offered_by
        offered_sticker.owner = receiver
        offered_sticker.is_trading = False
        offered_sticker.save(update_fields=["owner", "is_trading"])

        accepting_sticker.owner = original_sender
        accepting_sticker.save(update_fields=["owner"])

        # Finalise offer
        offer.status = TradeOffer.Status.ACCEPTED
        offer.resolved_at = datetime.now(tz=timezone.utc)
        offer.save(update_fields=["status", "resolved_at"])

        # Write history record
        TradeHistory.objects.create(
            offer=offer,
            from_user=original_sender,
            to_user=receiver,
            sticker_given=offered_sticker,
            sticker_received=accepting_sticker,
        )

        # Badge tracking: increment trades_completed for both parties
        User.objects.filter(pk__in=[original_sender.pk, receiver.pk]).update(
            trades_completed=F("trades_completed") + 1
        )

        logger.info(
            "Trade #%d completed: %s ↔ %s",
            offer.pk,
            original_sender,
            receiver,
        )
        return offered_sticker, accepting_sticker

    @transaction.atomic
    def reject_trade(self, receiver: User, offer: TradeOffer) -> TradeOffer:
        """Reject a trade offer — offered sticker is unlisted."""
        offer = TradeOffer.objects.select_for_update().get(pk=offer.pk)
        if offer.status != TradeOffer.Status.PENDING:
            raise ValueError("This offer is not pending")

        offered_sticker = Sticker.objects.get(pk=offer.offered_sticker_id)
        offered_sticker.is_trading = False
        offered_sticker.save(update_fields=["is_trading"])

        offer.status = TradeOffer.Status.REJECTED
        offer.resolved_at = datetime.now(tz=timezone.utc)
        offer.save(update_fields=["status", "resolved_at"])

        logger.info("Trade #%d rejected by %s", offer.pk, receiver)
        return offer

    @transaction.atomic
    def cancel_trade(self, user: User, offer: TradeOffer) -> TradeOffer:
        """Cancel a trade offer — only the original offerer can cancel."""
        offer = TradeOffer.objects.select_for_update().get(pk=offer.pk)
        if offer.offered_by != user:
            raise ValueError("Only the trade creator can cancel this offer")
        if offer.status != TradeOffer.Status.PENDING:
            raise ValueError("This offer is not pending")

        offered_sticker = Sticker.objects.get(pk=offer.offered_sticker_id)
        offered_sticker.is_trading = False
        offered_sticker.save(update_fields=["is_trading"])

        offer.status = TradeOffer.Status.CANCELLED
        offer.resolved_at = datetime.now(tz=timezone.utc)
        offer.save(update_fields=["status", "resolved_at"])

        logger.info("Trade #%d cancelled by %s", offer.pk, user)
        return offer

    def get_open_offers(self, user: User | None = None):
        """Return pending trade offers, optionally filtered to a specific user."""
        qs = TradeOffer.objects.filter(status=TradeOffer.Status.PENDING).select_related(
            "offered_sticker__pokemon",
            "offered_by",
            "offered_to",
        )
        if user is not None:
            qs = qs.filter(offered_to=user) | qs.filter(offered_to__isnull=True, offered_by=user)
        return qs.order_by("-created_at")


# ---------------------------------------------------------------------------
# AlbumService — regional album placement, completion, and rewards
# ---------------------------------------------------------------------------

class AlbumService:
    """
    Handles regional album page logic:
      - Placing / removing stickers into album slots
      - Page completion detection
      - Reward claiming per (region, rarity) page
      - Region index summary for the album hub page
    """

    # ------------------------------------------------------------------
    # Public read methods
    # ------------------------------------------------------------------

    def get_region_index(self, user: User) -> list[dict]:
        """
        Return a summary of all regions for the album hub.

        Each entry:
          {
            "region": str,
            "label": str,
            "dex_range": str,          # e.g. "#1 – #151"
            "locked": bool,            # True if no Pokemon exist in DB for this region
            "total_pokemon": int,
            "rarities": [
              {
                "rarity": str,
                "label": str,
                "placed": int,
                "total": int,
                "complete": bool,
                "reward_claimed": bool,
              }
            ],
            "pages_complete": int,
            "pages_total": int,
          }
        """
        from apps.pokemon.models import Pokemon

        all_pokemon = list(Pokemon.objects.only("pokedex_number").order_by("pokedex_number"))

        # Pre-fetch this user's placed stickers grouped by (region, rarity)
        placed_qs = (
            Sticker.objects.filter(owner=user, is_album_placed=True)
            .select_related("pokemon")
            .values("pokemon__pokedex_number", "rarity")
        )
        # Build set of (region, rarity, pokedex_number) for fast lookup
        placed_set: set[tuple[str, str, int]] = set()
        for row in placed_qs:
            dex = row["pokemon__pokedex_number"]
            if dex is None:
                continue
            for region_name, (low, high) in REGION_RANGES.items():
                if low <= dex <= high:
                    placed_set.add((region_name, row["rarity"], dex))
                    break

        # Pre-fetch claimed pages
        claimed_pages: set[tuple[str, str]] = set(
            RegionalAlbumPage.objects.filter(user=user, reward_claimed=True)
            .values_list("region", "rarity")
        )

        result = []
        for region_name, (low, high) in REGION_RANGES.items():
            region_pokemon = [p for p in all_pokemon if p.pokedex_number and low <= p.pokedex_number <= high]
            total_pokemon = len(region_pokemon)
            locked = total_pokemon == 0

            rarity_rows = []
            pages_complete = 0
            for rarity in StickerRarity.values:
                placed_count = sum(
                    1 for p in region_pokemon
                    if (region_name, rarity, p.pokedex_number) in placed_set
                )
                complete = total_pokemon > 0 and placed_count == total_pokemon
                if complete:
                    pages_complete += 1
                rarity_rows.append({
                    "rarity": rarity,
                    "label": StickerRarity(rarity).label,
                    "placed": placed_count,
                    "total": total_pokemon,
                    "complete": complete,
                    "reward_claimed": (region_name, rarity) in claimed_pages,
                })

            result.append({
                "region": region_name,
                "label": REGION_LABELS[region_name],
                "dex_range": f"#{low} – #{min(high, 99999) if high < 99999 else '???'}",
                "locked": locked,
                "total_pokemon": total_pokemon,
                "rarities": rarity_rows,
                "pages_complete": pages_complete,
                "pages_total": len(StickerRarity.values),
            })

        return result

    def get_page_detail(self, user: User, region: str, rarity: str) -> dict:
        """
        Return the full grid for one (region, rarity) album page.

        Returns:
          {
            "region": str,
            "region_label": str,
            "rarity": str,
            "rarity_label": str,
            "slots": [
              {
                "pokemon": Pokemon,
                "placed_sticker": Sticker | None,
                "available_stickers": list[Sticker],  # unplaced copies user owns
              }
            ],
            "placed_count": int,
            "total_count": int,
            "page_complete": bool,
            "reward_claimed": bool,
          }
        """
        from apps.pokemon.models import Pokemon

        if region not in REGION_RANGES:
            raise ValueError(f"Unknown region: {region}")
        if rarity not in StickerRarity.values:
            raise ValueError(f"Unknown rarity: {rarity}")

        low, high = REGION_RANGES[region]
        region_pokemon = list(
            Pokemon.objects.filter(
                pokedex_number__gte=low,
                pokedex_number__lte=high,
            ).order_by("pokedex_number")
        )

        # Placed stickers per (pokemon_id, variant): each slot is (pokemon, rarity, variant)
        placed_qs = Sticker.objects.filter(
            owner=user,
            rarity=rarity,
            is_album_placed=True,
            pokemon__pokedex_number__gte=low,
            pokemon__pokedex_number__lte=high,
        ).select_related("pokemon")
        # key: (pokemon_id, variant) → Sticker
        placed_map: dict[tuple[int, str], Sticker] = {
            (s.pokemon_id, s.variant): s for s in placed_qs
        }

        # Available (unplaced, non-trading) stickers per (pokemon_id, variant)
        available_qs = Sticker.objects.filter(
            owner=user,
            rarity=rarity,
            is_album_placed=False,
            is_trading=False,
            pokemon__pokedex_number__gte=low,
            pokemon__pokedex_number__lte=high,
        ).select_related("pokemon").order_by("pokemon__pokedex_number", "variant")

        # key: (pokemon_id, variant) → list[Sticker]
        available_map: dict[tuple[int, str], list[Sticker]] = {}
        for s in available_qs:
            key = (s.pokemon_id, s.variant)
            available_map.setdefault(key, []).append(s)

        # Build slots: one per (pokemon, variant) combination
        slots = []
        for pokemon in region_pokemon:
            for variant in _COMPLETION_VARIANTS:
                key = (pokemon.pk, variant)
                slots.append({
                    "pokemon": pokemon,
                    "variant": variant,
                    "variant_label": StickerVariant(variant).label,
                    "placed_sticker": placed_map.get(key),
                    "available_stickers": available_map.get(key, []),
                })

        placed_count = len(placed_map)
        # Total slots = one per (pokemon, variant) combination
        total_count = len(region_pokemon) * len(_COMPLETION_VARIANTS)
        page_complete = total_count > 0 and placed_count == total_count

        reward_claimed = RegionalAlbumPage.objects.filter(
            user=user, region=region, rarity=rarity, reward_claimed=True
        ).exists()

        return {
            "region": region,
            "region_label": REGION_LABELS.get(region, region.title()),
            "rarity": rarity,
            "rarity_label": StickerRarity(rarity).label,
            "slots": slots,
            "placed_count": placed_count,
            "total_count": total_count,
            "page_complete": page_complete,
            "reward_claimed": reward_claimed,
        }

    # ------------------------------------------------------------------
    # Mutating methods
    # ------------------------------------------------------------------

    @transaction.atomic
    def place_sticker(self, user: User, sticker_id: int) -> Sticker:
        """
        Place a sticker into its regional album slot.

        Validation:
        - User owns the sticker
        - Sticker is not already placed, not in trade
        - The pokemon has a valid region
        - No other placed sticker already occupies this (pokemon, rarity) slot
        - After placing, user must still have at least one unplaced copy
          (last-copy protection: you need N+1 total if you want to place one)

        Sets is_album_placed=True and checks for page completion.
        Returns the updated sticker.
        """
        sticker = Sticker.objects.select_for_update().filter(pk=sticker_id, owner=user).first()
        if sticker is None:
            raise ValueError("Sticker not found or does not belong to you")
        if sticker.is_album_placed:
            raise ValueError("This sticker is already placed in your album")
        if sticker.is_trading:
            raise ValueError("Cannot place a sticker that is currently in a trade")

        pokemon = sticker.pokemon
        if pokemon.region is None:
            raise ValueError(f"{pokemon.name} does not have a valid Pokédex number and cannot be placed")

        # Each (pokemon, rarity, variant) is a unique album slot.
        # Check no other placed sticker already fills this exact slot.
        already_placed = Sticker.objects.filter(
            owner=user,
            pokemon=pokemon,
            rarity=sticker.rarity,
            variant=sticker.variant,
            is_album_placed=True,
        ).exclude(pk=sticker.pk).exists()
        if already_placed:
            raise ValueError(
                f"You already have a {sticker.rarity} {sticker.variant} {pokemon.name} placed in your album"
            )
        # No last-copy restriction — placing your only copy makes it soul-bound (protected).

        sticker.is_album_placed = True
        sticker.save(update_fields=["is_album_placed"])

        logger.info(
            "Player %s placed sticker #%d (%s [%s]) in regional album",
            user,
            sticker.pk,
            pokemon.name,
            sticker.rarity,
        )

        # Award trainer XP for placing a sticker (10 XP per placement)
        from apps.users.services import award_trainer_xp
        award_trainer_xp(user, 10, source="sticker_placed")

        self._check_and_mark_page_complete(user, pokemon.region, sticker.rarity)
        return sticker

    @transaction.atomic
    def remove_sticker(self, user: User, sticker_id: int) -> Sticker:
        """
        Remove a sticker from its album slot, making it flexible again.

        Sets is_album_placed=False. Also clears completed_at on the page
        if it was complete (removing a sticker breaks completion).
        """
        sticker = Sticker.objects.select_for_update().filter(pk=sticker_id, owner=user).first()
        if sticker is None:
            raise ValueError("Sticker not found or does not belong to you")
        if not sticker.is_album_placed:
            raise ValueError("This sticker is not placed in your album")

        region = sticker.pokemon.region
        rarity = sticker.rarity

        sticker.is_album_placed = False
        sticker.save(update_fields=["is_album_placed"])

        # Unmark the page as complete if it was complete
        if region:
            RegionalAlbumPage.objects.filter(
                user=user, region=region, rarity=rarity
            ).update(completed_at=None)

        logger.info(
            "Player %s removed sticker #%d (%s [%s]) from regional album",
            user,
            sticker.pk,
            sticker.pokemon.name,
            rarity,
        )
        return sticker

    @transaction.atomic
    def claim_page_reward(self, user: User, region: str, rarity: str) -> dict:
        """
        Claim the reward for a completed (region, rarity) page.

        Validates:
        - Region and rarity are valid
        - Page is actually complete
        - Reward has not already been claimed

        Awards dust, ryo, and/or packs. Returns the reward amounts.
        """
        if region not in REGION_RANGES:
            raise ValueError(f"Unknown region: {region}")
        if rarity not in StickerRarity.values:
            raise ValueError(f"Unknown rarity: {rarity}")

        page_data = self.get_page_detail(user, region, rarity)
        if not page_data["page_complete"]:
            raise ValueError("This album page is not yet complete")

        page, created = RegionalAlbumPage.objects.get_or_create(
            user=user,
            region=region,
            rarity=rarity,
        )
        if not created and page.reward_claimed:
            raise ValueError("Reward for this page has already been claimed")

        reward = PAGE_REWARDS[rarity]
        dust = reward["dust"]
        ryo = reward["ryo"]
        packs = reward["packs"]

        user_obj = User.objects.select_for_update().get(pk=user.pk)
        user_obj.sticker_dust += dust
        user_obj.ryo += ryo
        user_obj.save(update_fields=["sticker_dust", "ryo"])

        for _ in range(packs):
            StickerPack.objects.create(owner=user_obj)

        page.reward_claimed = True
        page.save(update_fields=["reward_claimed"])

        logger.info(
            "Player %s claimed page reward for %s [%s]: dust=%d ryo=%d packs=%d",
            user,
            region,
            rarity,
            dust,
            ryo,
            packs,
        )
        return {"dust": dust, "ryo": ryo, "packs": packs}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _check_and_mark_page_complete(self, user: User, region: str, rarity: str) -> bool:
        """
        Check if the page is now complete and stamp completed_at if so.
        Returns True if page just became complete, False otherwise.
        """
        from datetime import datetime, timezone as tz

        from apps.pokemon.models import Pokemon

        low, high = REGION_RANGES[region]
        total_in_region = Pokemon.objects.filter(
            pokedex_number__gte=low,
            pokedex_number__lte=high,
        ).count()

        if total_in_region == 0:
            return False

        # Each slot = (pokemon, rarity, variant): total slots = pokemon_count × variant_count
        total_slots = total_in_region * len(_COMPLETION_VARIANTS)
        placed_count = Sticker.objects.filter(
            owner=user,
            rarity=rarity,
            is_album_placed=True,
            pokemon__pokedex_number__gte=low,
            pokemon__pokedex_number__lte=high,
            variant__in=_COMPLETION_VARIANTS,
        ).values("pokemon_id", "variant").distinct().count()

        if placed_count < total_slots:
            return False

        page, _ = RegionalAlbumPage.objects.get_or_create(
            user=user, region=region, rarity=rarity
        )
        if page.completed_at is None:
            page.completed_at = datetime.now(tz=tz.utc)
            page.save(update_fields=["completed_at"])
            logger.info(
                "Regional album page complete: user=%s region=%s rarity=%s",
                user,
                region,
                rarity,
            )
        return True


# ---------------------------------------------------------------------------
# SceneAlbumService — scene-page (15 Pokémon + card-flip) logic
# ---------------------------------------------------------------------------

class SceneAlbumService:
    """
    Handles data retrieval for the scene-based album pages.

    Each AlbumPage groups ~15 Pokémon into a location scene.  Within a scene
    the user browses by rarity (tab); each Pokémon card can be flipped to
    reveal its 6 variant slots for the current rarity.
    """

    def get_region_pages(self, region: str) -> list[AlbumPage]:
        """Return all AlbumPage objects for a region, ordered by page_number."""
        return list(AlbumPage.objects.filter(region=region).order_by("page_number"))

    def get_scene_page(self, user: User, album_page: AlbumPage, rarity: str) -> dict:
        """
        Build full context for one scene page at a given rarity.

        Returns:
          {
            "album_page": AlbumPage,
            "rarity": str,
            "rarity_label": str,
            "rarity_choices": list[tuple],
            "pokemon_cards": [
              {
                "pokemon": Pokemon,
                "variant_slots": [          # 6 entries, one per completion variant
                  {
                    "variant": str,
                    "variant_label": str,
                    "placed_sticker": Sticker | None,
                    "available_stickers": list[Sticker],
                  }
                ],
                "placed_count": int,        # how many variants placed at this rarity
                "total_variants": int,      # always 6
                "all_placed": bool,
              }
            ],
            "page_placed_count": int,       # total placed cells on this page at this rarity
            "page_total_count": int,        # total cells (pokemon_count × 6)
            "page_complete": bool,
            "reward_claimed": bool,
            "prev_page": AlbumPage | None,
            "next_page": AlbumPage | None,
          }
        """
        from apps.pokemon.models import Pokemon

        if rarity not in StickerRarity.values:
            raise ValueError(f"Unknown rarity: {rarity}")

        low, high = album_page.dex_start, album_page.dex_end
        region_pokemon = list(
            Pokemon.objects.filter(
                pokedex_number__gte=low,
                pokedex_number__lte=high,
            ).order_by("pokedex_number")
        )

        # Placed stickers: keyed by (pokemon_id, variant)
        placed_map: dict[tuple[int, str], Sticker] = {
            (s.pokemon_id, s.variant): s
            for s in Sticker.objects.filter(
                owner=user,
                rarity=rarity,
                is_album_placed=True,
                pokemon__pokedex_number__gte=low,
                pokemon__pokedex_number__lte=high,
            ).select_related("pokemon")
        }

        # Available unplaced stickers: keyed by (pokemon_id, variant)
        available_map: dict[tuple[int, str], list[Sticker]] = {}
        for s in Sticker.objects.filter(
            owner=user,
            rarity=rarity,
            is_album_placed=False,
            is_trading=False,
            pokemon__pokedex_number__gte=low,
            pokemon__pokedex_number__lte=high,
        ).select_related("pokemon").order_by("pokemon__pokedex_number", "variant"):
            available_map.setdefault((s.pokemon_id, s.variant), []).append(s)

        # Build per-Pokémon card data
        pokemon_cards = []
        for pokemon in region_pokemon:
            variant_slots = []
            placed_count = 0
            for variant in _COMPLETION_VARIANTS:
                key = (pokemon.pk, variant)
                placed = placed_map.get(key)
                if placed:
                    placed_count += 1
                variant_slots.append({
                    "variant": variant,
                    "variant_label": StickerVariant(variant).label,
                    "placed_sticker": placed,
                    "available_stickers": available_map.get(key, []),
                })
            pokemon_cards.append({
                "pokemon": pokemon,
                "variant_slots": variant_slots,
                "placed_count": placed_count,
                "total_variants": len(_COMPLETION_VARIANTS),
                "all_placed": placed_count == len(_COMPLETION_VARIANTS),
            })

        total_cells = len(region_pokemon) * len(_COMPLETION_VARIANTS)
        page_placed = len(placed_map)
        page_complete = total_cells > 0 and page_placed == total_cells

        reward_claimed = RegionalAlbumPage.objects.filter(
            user=user,
            region=album_page.region,
            rarity=rarity,
            reward_claimed=True,
        ).exists()

        # Prev / next page navigation
        siblings = list(
            AlbumPage.objects.filter(region=album_page.region).order_by("page_number")
        )
        idx = next((i for i, p in enumerate(siblings) if p.pk == album_page.pk), 0)
        prev_page = siblings[idx - 1] if idx > 0 else None
        next_page = siblings[idx + 1] if idx < len(siblings) - 1 else None

        return {
            "album_page": album_page,
            "rarity": rarity,
            "rarity_label": StickerRarity(rarity).label,
            "rarity_choices": StickerRarity.choices,
            "pokemon_cards": pokemon_cards,
            "page_placed_count": page_placed,
            "page_total_count": total_cells,
            "page_complete": page_complete,
            "reward_claimed": reward_claimed,
            "prev_page": prev_page,
            "next_page": next_page,
        }

    def get_all_pages_summary(self, user: User, region: str) -> list[dict]:
        """
        Return a summary of all pages in a region for the page-picker index.

        Each entry:
          {
            "album_page": AlbumPage,
            "rarity_progress": [{rarity, placed, total, complete, pct}],
            "overall_placed": int,
            "overall_total": int,
          }
        """
        from apps.pokemon.models import Pokemon

        pages = self.get_region_pages(region)
        if not pages:
            return []

        # All placed stickers in this region, grouped for fast lookup
        placed_qs = (
            Sticker.objects.filter(
                owner=user,
                is_album_placed=True,
                pokemon__pokedex_number__gte=pages[0].dex_start,
                pokemon__pokedex_number__lte=pages[-1].dex_end,
                variant__in=_COMPLETION_VARIANTS,
            )
            .values("pokemon__pokedex_number", "rarity", "variant")
        )
        # Build a set of (dex, rarity, variant) tuples for fast membership test
        placed_set: set[tuple[int, str, str]] = {
            (row["pokemon__pokedex_number"], row["rarity"], row["variant"])
            for row in placed_qs
            if row["pokemon__pokedex_number"] is not None
        }

        result = []
        for page in pages:
            pokemon_in_page = list(
                Pokemon.objects.filter(
                    pokedex_number__gte=page.dex_start,
                    pokedex_number__lte=page.dex_end,
                ).values_list("pokedex_number", flat=True)
            )
            poke_count = len(pokemon_in_page)
            total_per_rarity = poke_count * len(_COMPLETION_VARIANTS)

            rarity_progress = []
            overall_placed = 0
            for rarity in StickerRarity.values:
                placed = sum(
                    1 for dex in pokemon_in_page
                    for variant in _COMPLETION_VARIANTS
                    if (dex, rarity, variant) in placed_set
                )
                overall_placed += placed
                complete = total_per_rarity > 0 and placed == total_per_rarity
                rarity_progress.append({
                    "rarity": rarity,
                    "label": StickerRarity(rarity).label,
                    "placed": placed,
                    "total": total_per_rarity,
                    "complete": complete,
                    "pct": round(placed / total_per_rarity * 100) if total_per_rarity else 0,
                })

            result.append({
                "album_page": page,
                "rarity_progress": rarity_progress,
                "overall_placed": overall_placed,
                "overall_total": poke_count * len(_COMPLETION_VARIANTS) * len(StickerRarity.values),
            })

        return result
