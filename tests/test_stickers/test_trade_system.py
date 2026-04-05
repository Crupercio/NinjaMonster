"""Tests for the TradeService peer-to-peer sticker trading system."""
import pytest
import allure

from apps.stickers.models import (
    Sticker,
    StickerRarity,
    StickerVariant,
    TradeHistory,
    TradeOffer,
)

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.sticker_factory import StickerFactory, TradeOfferFactory


def _make_pair(player, pokemon, rarity=StickerRarity.COMMON, variant=StickerVariant.BASE):
    """Helper: create 2 identical stickers owned by `player` (a duplicate pair)."""
    s1 = StickerFactory(owner=player, pokemon=pokemon, rarity=rarity, variant=variant)
    s2 = StickerFactory(owner=player, pokemon=pokemon, rarity=rarity, variant=variant)
    return s1, s2


# ===========================================================================
# TradeService — create_trade_offer
# ===========================================================================

@allure.epic("Stickers")
@allure.feature("Trade System")
class TestCreateTradeOffer(BaseTest):

    @allure.story("Sender with duplicate can create a trade offer")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_create_offer_success(self, trade_svc, player, bulbasaur):
        # Arrange — need 2 copies so the service allows it
        s1, _s2 = _make_pair(player, bulbasaur)

        # Act
        offer = trade_svc.create_trade_offer(sender=player, sticker=s1)

        # Assert
        assert offer.pk is not None
        assert offer.offered_by == player
        assert offer.offered_sticker == s1
        assert offer.status == TradeOffer.Status.PENDING
        s1.refresh_from_db()
        assert s1.is_trading is True

    @allure.story("Creating offer for a sticker you don't own raises ValueError")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_create_offer_not_owner(self, trade_svc, player, other_player, bulbasaur):
        sticker = StickerFactory(owner=other_player, pokemon=bulbasaur)

        with pytest.raises(ValueError, match="do not own"):
            trade_svc.create_trade_offer(sender=player, sticker=sticker)

    @allure.story("Creating offer for your only copy raises ValueError")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_create_offer_only_copy(self, trade_svc, player, bulbasaur):
        sticker = StickerFactory(owner=player, pokemon=bulbasaur)

        with pytest.raises(ValueError, match="only copy"):
            trade_svc.create_trade_offer(sender=player, sticker=sticker)

    @allure.story("Creating offer for a sticker already in trade raises ValueError")
    @allure.severity(allure.severity_level.NORMAL)
    def test_create_offer_already_trading(self, trade_svc, player, bulbasaur):
        s1, _s2 = _make_pair(player, bulbasaur)
        s1.is_trading = True
        s1.save(update_fields=["is_trading"])

        with pytest.raises(ValueError, match="already listed"):
            trade_svc.create_trade_offer(sender=player, sticker=s1)


# ===========================================================================
# TradeService — accept_trade
# ===========================================================================

@allure.epic("Stickers")
@allure.feature("Trade System")
class TestAcceptTrade(BaseTest):

    @allure.story("Accepting a trade swaps ownership atomically")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_accept_trade_swaps_ownership(
        self, trade_svc, player, other_player, bulbasaur, charmander
    ):
        # Arrange
        sender_s1, sender_s2 = _make_pair(player, bulbasaur)
        receiver_s1, receiver_s2 = _make_pair(other_player, charmander)

        offer = trade_svc.create_trade_offer(sender=player, sticker=sender_s1)

        # Act
        given, received = trade_svc.accept_trade(
            receiver=other_player, offer=offer, accepting_sticker=receiver_s1
        )

        # Assert — ownership swapped
        given.refresh_from_db()
        received.refresh_from_db()
        assert given.owner == other_player       # sender's sticker now owned by receiver
        assert received.owner == player          # receiver's sticker now owned by sender
        assert given.is_trading is False

    @allure.story("Accepting a trade creates a TradeHistory record")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_accept_trade_creates_history(
        self, trade_svc, player, other_player, bulbasaur, charmander
    ):
        sender_s1, _sender_s2 = _make_pair(player, bulbasaur)
        receiver_s1, _receiver_s2 = _make_pair(other_player, charmander)

        offer = trade_svc.create_trade_offer(sender=player, sticker=sender_s1)
        trade_svc.accept_trade(
            receiver=other_player, offer=offer, accepting_sticker=receiver_s1
        )

        history = TradeHistory.objects.filter(offer=offer).first()
        assert history is not None
        assert history.from_user == player
        assert history.to_user == other_player

    @allure.story("Accepting a non-pending offer raises ValueError")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_accept_already_accepted_offer(
        self, trade_svc, player, other_player, bulbasaur, charmander
    ):
        sender_s1, _sender_s2 = _make_pair(player, bulbasaur)
        receiver_s1, receiver_s2 = _make_pair(other_player, charmander)

        offer = trade_svc.create_trade_offer(sender=player, sticker=sender_s1)
        trade_svc.accept_trade(
            receiver=other_player, offer=offer, accepting_sticker=receiver_s1
        )

        # Try to accept again with the second copy
        with pytest.raises(ValueError, match="no longer pending"):
            trade_svc.accept_trade(
                receiver=other_player, offer=offer, accepting_sticker=receiver_s2
            )

    @allure.story("Accepting with a sticker you don't own raises ValueError")
    @allure.severity(allure.severity_level.NORMAL)
    def test_accept_trade_not_owner(
        self, trade_svc, player, other_player, bulbasaur, charmander
    ):
        sender_s1, _sender_s2 = _make_pair(player, bulbasaur)
        # sticker actually owned by 'player', not 'other_player'
        foreign_sticker = StickerFactory(owner=player, pokemon=charmander)

        offer = trade_svc.create_trade_offer(sender=player, sticker=sender_s1)

        with pytest.raises(ValueError, match="do not own"):
            trade_svc.accept_trade(
                receiver=other_player, offer=offer, accepting_sticker=foreign_sticker
            )

    @allure.story("Accepting with your only copy of a sticker raises ValueError")
    @allure.severity(allure.severity_level.NORMAL)
    def test_accept_trade_only_copy(
        self, trade_svc, player, other_player, bulbasaur, charmander
    ):
        sender_s1, _sender_s2 = _make_pair(player, bulbasaur)
        receiver_only = StickerFactory(owner=other_player, pokemon=charmander)

        offer = trade_svc.create_trade_offer(sender=player, sticker=sender_s1)

        with pytest.raises(ValueError, match="only copy"):
            trade_svc.accept_trade(
                receiver=other_player, offer=offer, accepting_sticker=receiver_only
            )


# ===========================================================================
# TradeService — reject_trade / cancel_trade
# ===========================================================================

@allure.epic("Stickers")
@allure.feature("Trade System")
class TestRejectCancelTrade(BaseTest):

    @allure.story("Rejecting a trade sets status to REJECTED and unlists sticker")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_reject_trade(self, trade_svc, player, other_player, bulbasaur):
        s1, _s2 = _make_pair(player, bulbasaur)
        offer = trade_svc.create_trade_offer(sender=player, sticker=s1)

        trade_svc.reject_trade(receiver=other_player, offer=offer)

        offer.refresh_from_db()
        assert offer.status == TradeOffer.Status.REJECTED
        s1.refresh_from_db()
        assert s1.is_trading is False

    @allure.story("Cancelling a trade by the sender unlists the sticker")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_cancel_trade(self, trade_svc, player, bulbasaur):
        s1, _s2 = _make_pair(player, bulbasaur)
        offer = trade_svc.create_trade_offer(sender=player, sticker=s1)

        trade_svc.cancel_trade(user=player, offer=offer)

        offer.refresh_from_db()
        assert offer.status == TradeOffer.Status.CANCELLED
        s1.refresh_from_db()
        assert s1.is_trading is False

    @allure.story("Non-sender cannot cancel a trade")
    @allure.severity(allure.severity_level.NORMAL)
    def test_cancel_trade_not_sender(self, trade_svc, player, other_player, bulbasaur):
        s1, _s2 = _make_pair(player, bulbasaur)
        offer = trade_svc.create_trade_offer(sender=player, sticker=s1)

        with pytest.raises(ValueError, match="Only the trade creator"):
            trade_svc.cancel_trade(user=other_player, offer=offer)

    @allure.story("Rejecting an already-resolved offer raises ValueError")
    @allure.severity(allure.severity_level.NORMAL)
    def test_reject_resolved_offer(self, trade_svc, player, other_player, bulbasaur):
        s1, _s2 = _make_pair(player, bulbasaur)
        offer = trade_svc.create_trade_offer(sender=player, sticker=s1)
        trade_svc.cancel_trade(user=player, offer=offer)

        with pytest.raises(ValueError, match="not pending"):
            trade_svc.reject_trade(receiver=other_player, offer=offer)
