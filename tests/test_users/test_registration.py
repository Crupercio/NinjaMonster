"""Tests for the trainer registration form and view."""
import allure
import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from tests.framework.base.base_test import BaseTest
from tests.framework.factories.user_factory import UserFactory

User = get_user_model()


# ===========================================================================
# RegistrationForm validation (unit tests via the form class directly)
# ===========================================================================

@allure.epic("Users")
@allure.feature("Registration Form")
class TestRegistrationForm(BaseTest):

    @allure.story("Valid data passes form validation")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_valid_registration_form(self):
        from apps.users.forms import RegistrationForm

        form = RegistrationForm(data={
            "username": "ash_ketchum",
            "email": "ash@pallet.town",
            "password": "pikachu123",
            "confirm_password": "pikachu123",
        })
        assert form.is_valid(), form.errors

    @allure.story("Mismatched passwords fails validation")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_passwords_must_match(self):
        from apps.users.forms import RegistrationForm

        form = RegistrationForm(data={
            "username": "misty",
            "email": "misty@cerulean.gym",
            "password": "starmie99",
            "confirm_password": "wrong_password",
        })
        assert not form.is_valid()
        assert "confirm_password" in form.errors

    @allure.story("Duplicate username is rejected")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_duplicate_username_rejected(self):
        from apps.users.forms import RegistrationForm

        UserFactory(username="brock")
        form = RegistrationForm(data={
            "username": "brock",
            "email": "brock@pewter.gym",
            "password": "onixrocks1",
            "confirm_password": "onixrocks1",
        })
        assert not form.is_valid()
        assert "username" in form.errors

    @allure.story("Username check is case-insensitive")
    @allure.severity(allure.severity_level.NORMAL)
    def test_username_case_insensitive(self):
        from apps.users.forms import RegistrationForm

        UserFactory(username="Giovanni")
        form = RegistrationForm(data={
            "username": "giovanni",
            "email": "giovanni@rocketbase.com",
            "password": "mewtwo123",
            "confirm_password": "mewtwo123",
        })
        assert not form.is_valid()
        assert "username" in form.errors

    @allure.story("Duplicate email is rejected")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_duplicate_email_rejected(self):
        from apps.users.forms import RegistrationForm

        UserFactory(email="nurse@pokemon.center")
        form = RegistrationForm(data={
            "username": "nurse_joy",
            "email": "nurse@pokemon.center",
            "password": "chansey123",
            "confirm_password": "chansey123",
        })
        assert not form.is_valid()
        assert "email" in form.errors

    @allure.story("Password shorter than 8 characters is rejected")
    @allure.severity(allure.severity_level.NORMAL)
    def test_password_min_length(self):
        from apps.users.forms import RegistrationForm

        form = RegistrationForm(data={
            "username": "gary_oak",
            "email": "gary@pallettown.com",
            "password": "short",
            "confirm_password": "short",
        })
        assert not form.is_valid()
        assert "password" in form.errors

    @allure.story("Empty username is rejected")
    @allure.severity(allure.severity_level.NORMAL)
    def test_empty_username_rejected(self):
        from apps.users.forms import RegistrationForm

        form = RegistrationForm(data={
            "username": "",
            "email": "oak@lab.com",
            "password": "pokemon123",
            "confirm_password": "pokemon123",
        })
        assert not form.is_valid()
        assert "username" in form.errors


# ===========================================================================
# RegisterView (integration tests via Django test client)
# ===========================================================================

@allure.epic("Users")
@allure.feature("Registration View")
class TestRegistrationView(BaseTest):

    @allure.story("GET /accounts/register/ returns 200")
    @allure.severity(allure.severity_level.NORMAL)
    def test_register_page_loads(self):
        client = Client()
        response = client.get(reverse("users:register"))
        assert response.status_code == 200

    @allure.story("Valid POST creates a new user and redirects to login")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_valid_post_creates_user(self):
        client = Client()
        response = client.post(reverse("users:register"), data={
            "username": "trainer_red",
            "email": "red@indigo.plateau",
            "password": "charizard99",
            "confirm_password": "charizard99",
        })
        assert response.status_code == 302
        assert "/login" in response["Location"] or "login" in response["Location"]
        assert User.objects.filter(username="trainer_red").exists()

    @allure.story("Valid POST sets correct display_name")
    @allure.severity(allure.severity_level.NORMAL)
    def test_registration_sets_display_name(self):
        client = Client()
        client.post(reverse("users:register"), data={
            "username": "trainer_blue",
            "email": "blue@indigo.plateau",
            "password": "blastoise99",
            "confirm_password": "blastoise99",
        })
        user = User.objects.get(username="trainer_blue")
        assert user.display_name == "trainer_blue"

    @allure.story("Invalid POST re-renders the form with errors")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_invalid_post_shows_errors(self):
        client = Client()
        response = client.post(reverse("users:register"), data={
            "username": "trainer_misty",
            "email": "misty@cerulean.gym",
            "password": "water1",
            "confirm_password": "water2",
        })
        assert response.status_code == 200  # stays on page
        assert not User.objects.filter(username="trainer_misty").exists()

    @allure.story("Duplicate username POST re-renders with error")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_duplicate_username_post(self):
        client = Client()
        UserFactory(username="taken_name")
        response = client.post(reverse("users:register"), data={
            "username": "taken_name",
            "email": "new@email.com",
            "password": "pokemon123",
            "confirm_password": "pokemon123",
        })
        assert response.status_code == 200
        assert User.objects.filter(username="taken_name").count() == 1
