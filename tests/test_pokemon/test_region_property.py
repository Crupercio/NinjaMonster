"""
Tests for Pokemon.region computed property.

Verifies all nine generation boundary values and edge cases.
"""
import pytest

from tests.framework.factories.pokemon_factory import PokemonFactory, PokemonTypeFactory


pytestmark = pytest.mark.django_db


class TestPokemonRegionProperty:
    """Pokemon.region must return correct region string for all dex ranges."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.ptype = PokemonTypeFactory(name="Normal")

    def _make(self, dex: int | None):
        return PokemonFactory(primary_type=self.ptype, pokedex_number=dex)

    # ── Boundary tests ─────────────────────────────────────────────
    def test_kanto_first(self):
        assert self._make(1).region == "kanto"

    def test_kanto_last(self):
        assert self._make(151).region == "kanto"

    def test_johto_first(self):
        assert self._make(152).region == "johto"

    def test_johto_last(self):
        assert self._make(251).region == "johto"

    def test_hoenn_first(self):
        assert self._make(252).region == "hoenn"

    def test_hoenn_last(self):
        assert self._make(386).region == "hoenn"

    def test_sinnoh_first(self):
        assert self._make(387).region == "sinnoh"

    def test_sinnoh_last(self):
        assert self._make(493).region == "sinnoh"

    def test_unova_first(self):
        assert self._make(494).region == "unova"

    def test_unova_last(self):
        assert self._make(649).region == "unova"

    def test_kalos_first(self):
        assert self._make(650).region == "kalos"

    def test_kalos_last(self):
        assert self._make(721).region == "kalos"

    def test_alola_first(self):
        assert self._make(722).region == "alola"

    def test_alola_last(self):
        assert self._make(809).region == "alola"

    def test_galar_first(self):
        assert self._make(810).region == "galar"

    def test_galar_last(self):
        assert self._make(905).region == "galar"

    def test_paldea_first(self):
        assert self._make(906).region == "paldea"

    def test_paldea_high_value(self):
        assert self._make(1025).region == "paldea"

    # ── Edge cases ─────────────────────────────────────────────────
    def test_none_pokedex_returns_none(self):
        poke = PokemonFactory(primary_type=self.ptype, pokedex_number=None)
        assert poke.region is None

    def test_midrange_kanto(self):
        assert self._make(25).region == "kanto"  # Pikachu

    def test_midrange_johto(self):
        assert self._make(152).region == "johto"  # Chikorita
