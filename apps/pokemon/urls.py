"""URL patterns for the pokemon app."""
from django.urls import path

from .views import (
    CatchPokemonView,
    MyPokemonView,
    OwnedPokemonDetailView,
    PokedexView,
    PokemonDetailView,
    SellPokemonView,
    TeamSlotPickerView,
    TeamView,
    TypeChartView,
)

app_name = "pokemon"

urlpatterns = [
    path("", PokedexView.as_view(), name="pokedex"),
    path("types/", TypeChartView.as_view(), name="type_chart"),
    path("<int:pk>/", PokemonDetailView.as_view(), name="detail"),
    path("<int:pk>/catch/", CatchPokemonView.as_view(), name="catch"),
    path("my/", MyPokemonView.as_view(), name="my_pokemon"),
    path("my/<int:pk>/", OwnedPokemonDetailView.as_view(), name="owned_detail"),
    path("my/<int:pk>/sell/", SellPokemonView.as_view(), name="sell"),
    path("team/", TeamView.as_view(), name="team"),
    path("team/slot/<int:position>/", TeamSlotPickerView.as_view(), name="team_slot"),
]
