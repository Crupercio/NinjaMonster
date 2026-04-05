"""factory_boy factory for the custom User model."""
import factory
from django.contrib.auth import get_user_model

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"trainer_{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    display_name = factory.LazyAttribute(lambda o: o.username.replace("_", " ").title())
    password = factory.PostGenerationMethodCall("set_password", "testpass123")
    is_active = True
