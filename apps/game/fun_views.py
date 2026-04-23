"""Views for collector arcade experiences under the Fun hub."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView

from apps.users.services import get_candy_inventory

from .fun import (
    abandon_memory_run,
    advance_silhouette_run,
    answer_silhouette_question,
    cash_out_silhouette_run,
    clear_memory_result_state,
    clear_silhouette_reveal_state,
    clear_silhouette_run_state,
    complete_memory_run,
    get_memory_board_catalog,
    get_memory_board_config,
    get_memory_result_state,
    get_memory_run_state,
    get_random_silhouette_species,
    get_silhouette_reveal_state,
    get_silhouette_run_state,
    get_silhouette_tower_catalog,
    get_silhouette_tower_config,
    get_tower_species_map,
    start_memory_run,
    start_silhouette_run,
)


def _pokemon_image_url(pokemon) -> str:
    """Best-effort artwork URL for silhouette and option previews."""
    if pokemon.sprite_url:
        return pokemon.sprite_url
    if pokemon.pokedex_number:
        return f"/media/pokemon/sprites/{pokemon.pokedex_number:03d}.png"
    return ""


class ComingSoonGameView(LoginRequiredMixin, TemplateView):
    """Placeholder collector arcade page for upcoming games."""

    template_name = "game/coming_soon_game.html"
    game_title = "Coming Soon"
    game_subtitle = "Collector arcade cabinet"
    game_logo = ""
    game_copy = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "game_title": self.game_title,
                "game_subtitle": self.game_subtitle,
                "game_logo": self.game_logo,
                "game_copy": self.game_copy,
                "candy_inventory": get_candy_inventory(self.request.user),
            }
        )
        return context


class MemoryMatchView(ComingSoonGameView):
    """Focused play page for one memory board."""

    template_name = "game/memory_game.html"
    board_mascots = {
        "rookie_3x4": "images/games/memory_board_rookie.gif",
        "standard_4x4": "images/games/memory_board_standard.gif",
        "collector_4x5": "images/games/memory_board_collector.gif",
        "master_6x4": "images/games/memory_board_master.gif",
    }

    def dispatch(self, request, *args, **kwargs):
        self.board_config = get_memory_board_config(kwargs["board_key"])
        if not self.board_config.enabled:
            messages.info(request, f"{self.board_config.title} is not open yet.")
            return redirect("game:memory_game")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        run_state = get_memory_run_state(self.request.session)
        board_run = run_state if run_state and run_state.get("board_key") == self.board_config.key else None
        result_state = get_memory_result_state(self.request.session)
        board_result = result_state if result_state and result_state.get("board_key") == self.board_config.key else None

        context.update(
            {
                "board": self.board_config,
                "board_run": board_run,
                "board_result": board_result,
                "candy_inventory": get_candy_inventory(self.request.user),
                "board_mascot": self.board_mascots.get(self.board_config.key, ""),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action", "")
        run_state = get_memory_run_state(request.session)
        board_run = run_state if run_state and run_state.get("board_key") == self.board_config.key else None
        return_url = reverse("game:memory_board", kwargs={"board_key": self.board_config.key})

        if action == "start_run":
            try:
                start_memory_run(request.user, request.session, self.board_config)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    f"{self.board_config.title} opened. {self.board_config.entry_qty} {self.board_config.entry_label} spent.",
                )
            return redirect(return_url)

        if action == "abandon":
            abandon_memory_run(request.session)
            clear_memory_result_state(request.session)
            messages.info(request, "The current memory board was cleared without claiming rewards.")
            return redirect(return_url)

        if action == "dismiss_result":
            clear_memory_result_state(request.session)
            return redirect(return_url)

        if action == "complete_run":
            if not board_run:
                messages.error(request, "Start a memory board before claiming rewards.")
                return redirect(return_url)
            try:
                turns = int(request.POST.get("turns", "0"))
                elapsed_seconds = int(request.POST.get("elapsed_seconds", "0"))
                best_streak = int(request.POST.get("best_streak", "0"))
            except ValueError:
                messages.error(request, "The memory board result could not be scored.")
                return redirect(return_url)

            result = complete_memory_run(
                request.user,
                request.session,
                self.board_config,
                board_run,
                turns=turns,
                elapsed_seconds=elapsed_seconds,
                best_streak=best_streak,
            )
            messages.success(
                request,
                f"{result['grade']} clear! You earned {result['reward_ryo']} Ryo and {result['reward_dust']} Dust.",
            )
            return redirect(return_url)

        messages.error(request, "Unknown memory board action.")
        return redirect(return_url)


class MemoryHubView(LoginRequiredMixin, TemplateView):
    """Board selection hub for the memory arcade."""

    template_name = "game/memory_hub.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        candy_inventory = get_candy_inventory(self.request.user)
        run_state = get_memory_run_state(self.request.session)
        result_state = get_memory_result_state(self.request.session)
        current_key = None
        if result_state and result_state.get("board_key"):
            current_key = result_state["board_key"]
        elif run_state and run_state.get("board_key"):
            current_key = run_state["board_key"]

        board_cards = []
        for board in get_memory_board_catalog():
            count = candy_inventory.get(board.entry_candy_type, {}).get("count", 0)
            board_cards.append(
                {
                    "config": board,
                    "entry_count": count,
                    "can_enter": count >= board.entry_qty,
                    "is_current": board.key == current_key,
                }
            )

        active_board = get_memory_board_config(current_key) if current_key else None
        context.update(
            {
                "candy_inventory": candy_inventory,
                "board_cards": board_cards,
                "active_memory_board": active_board,
            }
        )
        return context


class LoteriaGameView(ComingSoonGameView):
    """Pokemon Loteria placeholder page."""

    game_title = "Pokemon Loteria"
    game_subtitle = "Luck game"
    game_logo = "loteria_game_logo.png"
    game_copy = (
        "A nostalgic draw-based game with themed boards, lucky hits, and higher-variance prize pulls."
    )


class SilhouetteHubView(LoginRequiredMixin, TemplateView):
    """Tower selection hub for the silhouette arcade."""

    template_name = "game/silhouette_hub.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        candy_inventory = get_candy_inventory(self.request.user)
        run_state = get_silhouette_run_state(self.request.session)
        reveal_state = get_silhouette_reveal_state(self.request.session)
        current_key = None
        if reveal_state and reveal_state.get("tower_key"):
            current_key = reveal_state["tower_key"]
        elif run_state and run_state.get("tower_key"):
            current_key = run_state["tower_key"]

        tower_silhouettes = get_random_silhouette_species(len(get_silhouette_tower_catalog()))
        tower_cards = []
        for idx, tower in enumerate(get_silhouette_tower_catalog()):
            count = candy_inventory.get(tower.entry_candy_type, {}).get("count", 0)
            silhouette_species = tower_silhouettes[idx] if idx < len(tower_silhouettes) else None
            tower_cards.append(
                {
                    "config": tower,
                    "entry_count": count,
                    "can_enter": count >= tower.entry_qty,
                    "is_current": tower.key == current_key,
                    "silhouette_url": _pokemon_image_url(silhouette_species) if silhouette_species else "",
                }
            )

        active_tower = get_silhouette_tower_config(current_key) if current_key else None
        context.update(
            {
                "candy_inventory": candy_inventory,
                "tower_cards": tower_cards,
                "active_silhouette_tower": active_tower,
            }
        )
        return context


class SilhouetteTowerView(LoginRequiredMixin, TemplateView):
    """Single reusable silhouette tower screen."""

    template_name = "game/silhouette_tower.html"

    def dispatch(self, request, *args, **kwargs):
        self.tower_config = get_silhouette_tower_config(kwargs["tower_key"])
        if not self.tower_config.enabled:
            messages.info(request, f"{self.tower_config.title} is not open yet.")
            return redirect("game:home")
        self.species_map = get_tower_species_map(self.tower_config)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        run_state = get_silhouette_run_state(self.request.session)
        tower_run = run_state if run_state and run_state.get("tower_key") == self.tower_config.key else None
        reveal_state = get_silhouette_reveal_state(self.request.session)
        tower_reveal = reveal_state if reveal_state and reveal_state.get("tower_key") == self.tower_config.key else None
        candy_inventory = get_candy_inventory(self.request.user)

        question_card = None
        option_cards: list[dict] = []
        reveal_mode = False
        auto_advance = False
        answer_result = None
        floor_display = tower_run["current_floor"] if tower_run else 1
        cleared_count = len(tower_run["asked_dex_numbers"]) if tower_run else 0
        banked_ryo = tower_run["banked_ryo"] if tower_run else 0

        if tower_reveal:
            reveal_mode = True
            auto_advance = tower_reveal.get("status") == "correct" and bool(tower_reveal.get("next_run_state"))
            answer_result = tower_reveal
            floor_display = tower_reveal.get("floor_answered", 1)
            banked_ryo = tower_reveal.get("banked_ryo", 0)
            question_dex = tower_reveal.get("correct_dex")
            question_species = self.species_map.get(question_dex)
            if question_species:
                question_card = {
                    "dex": question_species.pokedex_number,
                    "name": question_species.name,
                    "image_url": _pokemon_image_url(question_species),
                    "reward": tower_reveal.get("reward", 0),
                }
            for dex in tower_reveal.get("option_dex_numbers", []):
                pokemon = self.species_map.get(dex)
                if pokemon is None:
                    continue
                option_cards.append(
                    {
                        "dex": pokemon.pokedex_number,
                        "name": pokemon.name,
                        "is_correct": pokemon.pokedex_number == tower_reveal.get("correct_dex"),
                        "is_selected": pokemon.pokedex_number == tower_reveal.get("selected_dex"),
                    }
                )
            if tower_reveal.get("status") == "correct":
                cleared_count = max(0, floor_display)
            elif tower_reveal.get("status") == "cleared":
                cleared_count = self.tower_config.max_floors
            else:
                cleared_count = max(0, floor_display - 1)
        elif tower_run:
            question = tower_run.get("question") or {}
            question_dex = question.get("correct_dex")
            question_species = self.species_map.get(question_dex)
            if question_species:
                floor_index = int(tower_run["current_floor"]) - 1
                question_card = {
                    "dex": question_species.pokedex_number,
                    "name": question_species.name,
                    "image_url": _pokemon_image_url(question_species),
                    "reward": self.tower_config.floor_rewards[floor_index],
                }

            for dex in question.get("option_dex_numbers", []):
                pokemon = self.species_map.get(dex)
                if pokemon is None:
                    continue
                option_cards.append(
                    {
                        "dex": pokemon.pokedex_number,
                        "name": pokemon.name,
                        "is_correct": False,
                        "is_selected": False,
                    }
                )

        context.update(
            {
                "tower": self.tower_config,
                "tower_run": tower_run,
                "tower_reveal": tower_reveal,
                "question_card": question_card,
                "option_cards": option_cards,
                "candy_inventory": candy_inventory,
                "species_count": self.tower_config.pool_size,
                "guess_background": f"images/games/guess_background_{((int(floor_display) - 1) % 6) + 1}.png" if (tower_run or tower_reveal) else "images/games/guess_background.png",
                "reveal_mode": reveal_mode,
                "auto_advance": auto_advance,
                "answer_result": answer_result,
                "floor_display": floor_display,
                "cleared_count": cleared_count,
                "banked_ryo_display": banked_ryo,
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action", "")
        run_state = get_silhouette_run_state(request.session)
        tower_run = run_state if run_state and run_state.get("tower_key") == self.tower_config.key else None
        reveal_state = get_silhouette_reveal_state(request.session)
        tower_reveal = reveal_state if reveal_state and reveal_state.get("tower_key") == self.tower_config.key else None
        return_url = reverse("game:silhouette_tower", kwargs={"tower_key": self.tower_config.key})

        if action == "start_run":
            try:
                start_silhouette_run(request.user, request.session, self.tower_config)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    f"{self.tower_config.title} started. {self.tower_config.entry_qty} {self.tower_config.entry_label} spent.",
                )
            return redirect(return_url)

        if action == "cash_out":
            if not tower_run:
                messages.info(request, "There is no active tower run to cash out.")
                return redirect(return_url)
            payout = cash_out_silhouette_run(request.user, request.session, tower_run)
            messages.success(request, f"You cashed out {payout} Ryo from {self.tower_config.title}.")
            return redirect(return_url)

        if action == "abandon":
            clear_silhouette_run_state(request.session)
            clear_silhouette_reveal_state(request.session)
            messages.info(request, "The current silhouette run was abandoned.")
            return redirect(return_url)

        if action == "advance":
            if not tower_reveal:
                return redirect(return_url)
            try:
                advance_silhouette_run(request.session, self.tower_config.key)
            except ValueError:
                pass
            return redirect(return_url)

        if action == "guess":
            if not tower_run or tower_reveal:
                messages.error(request, "Start a tower run before making a guess.")
                return redirect(return_url)
            try:
                selected_dex = int(request.POST.get("selected_dex", "0"))
            except ValueError:
                messages.error(request, "Choose one of the six options to answer.")
                return redirect(return_url)

            result = answer_silhouette_question(
                request.user,
                request.session,
                self.tower_config,
                tower_run,
                selected_dex,
            )
            correct_species = self.species_map.get(result["correct_dex"])
            correct_name = correct_species.name if correct_species else "that silhouette"

            if result["status"] == "cleared":
                messages.success(request, f"Tower cleared! {correct_name} finished the climb. You earned {result['payout']} Ryo.")
            elif result["status"] == "wrong":
                messages.error(request, f"Wrong. It was {correct_name}. You salvaged {result['payout']} Ryo from the run.")
            return redirect(return_url)

        messages.error(request, "Unknown tower action.")
        return redirect(return_url)
