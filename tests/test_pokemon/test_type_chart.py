"""
P2-5 — Type chart in UI tests.

Covers:
- get_effectiveness returns 2.0 for super-effective matchups
- get_effectiveness returns 0.5 for not-very-effective matchups
- get_effectiveness returns 0.0 for immune matchups
- get_effectiveness returns 1.0 for neutral matchups
- build_chart_matrix returns 18 rows, each with 18 cells
- TypeChartView returns 200 without focus param
- TypeChartView returns 200 with valid ?focus=Fire param
- TypeChartView context includes focus_detail when focus is set
- TypeChartView context focus_type is empty string for invalid focus
"""
import allure
import pytest
from django.test import Client
from django.urls import reverse

from apps.pokemon.type_chart import ALL_TYPES, build_chart_matrix, get_effectiveness

from tests.framework.base.base_test import BaseTest


def _client():
    return Client()


@allure.epic("Pokedex")
@allure.feature("Type Chart")
class TestGetEffectiveness(BaseTest):

    @allure.story("Returns 2.0 for super-effective matchup")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_super_effective(self):
        # Fire vs Grass is 2×
        assert get_effectiveness("Fire", "Grass") == 2.0

    @allure.story("Returns 0.5 for not-very-effective matchup")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_not_very_effective(self):
        # Fire vs Water is ½
        assert get_effectiveness("Fire", "Water") == 0.5

    @allure.story("Returns 0.0 for immune matchup")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_immune(self):
        # Electric vs Ground is 0
        assert get_effectiveness("Electric", "Ground") == 0.0

    @allure.story("Returns 1.0 for neutral matchup")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_neutral(self):
        # Normal vs Normal is 1
        assert get_effectiveness("Normal", "Normal") == 1.0

    @allure.story("Symmetric: known super-effective pair")
    @allure.severity(allure.severity_level.NORMAL)
    def test_water_beats_fire(self):
        assert get_effectiveness("Water", "Fire") == 2.0


@allure.epic("Pokedex")
@allure.feature("Type Chart")
class TestBuildChartMatrix(BaseTest):

    @allure.story("Returns 18 rows each with 18 cells")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_matrix_dimensions(self):
        matrix = build_chart_matrix()
        assert len(matrix) == 18
        for row in matrix:
            assert len(row["cells"]) == 18

    @allure.story("All 18 attacker names present")
    @allure.severity(allure.severity_level.NORMAL)
    def test_all_attacker_names(self):
        matrix = build_chart_matrix()
        attackers = [row["attacker"] for row in matrix]
        assert set(attackers) == set(ALL_TYPES)


@allure.epic("Pokedex")
@allure.feature("Type Chart")
@pytest.mark.django_db
class TestTypeChartView(BaseTest):

    @allure.story("Returns 200 without focus param")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_plain_200(self):
        response = _client().get(reverse("pokemon:type_chart"))
        assert response.status_code == 200

    @allure.story("Returns 200 with valid ?focus=Fire")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_focus_200(self):
        response = _client().get(reverse("pokemon:type_chart") + "?focus=Fire")
        assert response.status_code == 200

    @allure.story("focus_detail present in context when focus is valid")
    @allure.severity(allure.severity_level.NORMAL)
    def test_focus_detail_in_context(self):
        response = _client().get(reverse("pokemon:type_chart") + "?focus=Fire")
        assert response.context["focus_type"] == "Fire"
        assert "focus_detail" in response.context
        detail = response.context["focus_detail"]
        assert "weak_to" in detail
        assert "resists" in detail
        # Fire is weak to Water
        assert "Water" in detail["weak_to"]

    @allure.story("focus_type is empty string for invalid focus value")
    @allure.severity(allure.severity_level.NORMAL)
    def test_invalid_focus_ignored(self):
        response = _client().get(reverse("pokemon:type_chart") + "?focus=Faketype")
        assert response.context["focus_type"] == ""
