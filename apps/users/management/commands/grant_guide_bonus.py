"""Grant missed 130k guide completion bonus to users who finished but didn't receive it."""
import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import F

from apps.users.guide_service import COMPLETION_BONUS, GUIDE_COMPLETE_STEP

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = "Grant the 130,000 Ryo guide completion bonus to a specific user."

    def add_arguments(self, parser):
        parser.add_argument("username", type=str, help="Username to grant the bonus to")

    def handle(self, *args, **options):
        username = options["username"]
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stderr.write(f"User '{username}' not found.")
            return

        if user.guide_step < GUIDE_COMPLETE_STEP:
            self.stderr.write(f"User '{username}' has not completed the guide (step={user.guide_step}).")
            return

        User.objects.filter(pk=user.pk).update(ryo=F("ryo") + COMPLETION_BONUS)
        self.stdout.write(self.style.SUCCESS(
            f"Granted {COMPLETION_BONUS:,} Ryo to '{username}'. New balance: {user.ryo + COMPLETION_BONUS:,}"
        ))
