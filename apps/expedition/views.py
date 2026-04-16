"""Views for the expedition system."""
import json
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView

from apps.users.services import get_candy_inventory

from .models import ExpeditionSession
from .services import draw_encounter, get_zones_for_user, resolve_encounter, start_expedition

logger = logging.getLogger(__name__)


class ExpeditionHubView(LoginRequiredMixin, TemplateView):
    """Zone selection hub — shows all zones with spawn previews."""

    template_name = "expedition/hub.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["zones"] = get_zones_for_user(user)
        context["candy"] = get_candy_inventory(user)
        context["trainer_level"] = user.trainer_level
        context["trainer_xp"] = user.trainer_xp
        context["trainer_xp_to_next"] = user.trainer_xp_to_next_level
        context["trainer_xp_percent"] = user.trainer_xp_percent
        context["max_expeditions"] = user.max_daily_expeditions
        return context


class StartExpeditionAPI(LoginRequiredMixin, View):
    """POST: pay entry fee and create session."""

    def post(self, request):
        try:
            body = json.loads(request.body)
            zone_pk = int(body.get("zone_id", 0))
        except (ValueError, KeyError):
            return JsonResponse({"error": "Invalid request."}, status=400)

        try:
            session = start_expedition(request.user, zone_pk)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        request.user.refresh_from_db(fields=["ryo"])
        return JsonResponse({
            "session_id": session.pk,
            "zone_name": session.zone.name,
            "flavor_intro": session.zone.flavor_intro,
            "flavor_walking": session.zone.flavor_walking,
            "encounters_total": session.encounters_total,
            "encounters_remaining": session.encounters_remaining,
            "ryo_remaining": request.user.ryo,
        })


class DrawEncounterAPI(LoginRequiredMixin, View):
    """GET: draw next encounter (does not consume a slot)."""

    def get(self, request, session_id: int):
        session = ExpeditionSession.objects.filter(
            pk=session_id, user=request.user
        ).select_related("zone").first()
        if session is None:
            return JsonResponse({"error": "Session not found."}, status=404)
        if session.is_finished:
            return JsonResponse({"finished": True, "encounters_remaining": 0})

        encounter = draw_encounter(session)
        encounter["encounters_remaining"] = session.encounters_remaining
        return JsonResponse(encounter)


class ResolveEncounterAPI(LoginRequiredMixin, View):
    """POST: attempt bond with optional candy. Consumes one encounter slot."""

    def post(self, request, session_id: int):
        session = ExpeditionSession.objects.filter(
            pk=session_id, user=request.user
        ).select_related("zone").first()
        if session is None:
            return JsonResponse({"error": "Session not found."}, status=404)

        try:
            body = json.loads(request.body)
            species_pk = int(body.get("species_id", 0))
            base_bond_rate = int(body.get("base_bond_rate", 50))
            candy_type = body.get("candy_type", "")
        except (ValueError, KeyError, TypeError):
            return JsonResponse({"error": "Invalid request."}, status=400)

        try:
            result = resolve_encounter(
                session=session,
                species_pk=species_pk,
                base_bond_rate=base_bond_rate,
                candy_type=candy_type,
            )
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        request.user.refresh_from_db()
        result["candy_trail_mix"] = request.user.candy_trail_mix
        result["candy_sweet_berry"] = request.user.candy_sweet_berry
        result["candy_golden_apple"] = request.user.candy_golden_apple
        result["trainer_level"] = request.user.trainer_level
        result["trainer_xp_percent"] = request.user.trainer_xp_percent
        return JsonResponse(result)
