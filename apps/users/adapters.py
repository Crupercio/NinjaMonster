"""Custom allauth adapters for the Users app."""
import logging
import re

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model
from django.http import HttpRequest

logger = logging.getLogger(__name__)

User = get_user_model()


class AccountAdapter(DefaultAccountAdapter):
    """Standard account adapter — no custom behaviour needed yet."""

    pass


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Handles Google OAuth sign-in.

    Responsibilities:
    - Auto-generate a unique username from the Google display name / email.
    - Link a Google login to an existing account if the email already exists.
    """

    def pre_social_login(self, request: HttpRequest, sociallogin: object) -> None:
        """
        If a user with this email already exists (e.g. registered via email/password),
        connect the Google account to that user instead of creating a duplicate.
        """
        email = sociallogin.account.extra_data.get("email", "").lower()
        if not email:
            return

        try:
            existing_user = User.objects.get(email=email)
        except User.DoesNotExist:
            return

        # Link this social account to the existing user and log them in.
        sociallogin.connect(request, existing_user)

    def populate_user(self, request: HttpRequest, sociallogin: object, data: dict) -> object:
        """Fill in the User fields from Google profile data."""
        user = super().populate_user(request, sociallogin, data)

        # Generate a username from the Google name or email prefix.
        if not getattr(user, "username", None):
            base = data.get("name") or data.get("email", "user").split("@")[0]
            user.username = self._unique_username(base)

        # Populate display_name from Google full name if not set.
        if not getattr(user, "display_name", None):
            user.display_name = data.get("name", "")

        return user

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _unique_username(base: str) -> str:
        """
        Derive a URL-safe username from *base* and append a numeric suffix
        if needed to make it unique.
        """
        slug = re.sub(r"[^\w]", "_", base).strip("_")[:28] or "trainer"
        username = slug
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{slug}_{counter}"
            counter += 1
        return username
