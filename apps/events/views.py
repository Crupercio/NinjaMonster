"""Views for the seasonal events framework."""
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from .services import SeasonalEventService

logger = logging.getLogger(__name__)
_event_service = SeasonalEventService()


class EventListView(LoginRequiredMixin, TemplateView):
    """GET /events/ — lists active, upcoming, and recently ended events."""

    template_name = "events/event_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_events"] = list(_event_service.get_active_events())
        context["upcoming_events"] = list(_event_service.get_upcoming_events())
        context["ended_events"] = list(_event_service.get_recent_ended_events())
        return context
