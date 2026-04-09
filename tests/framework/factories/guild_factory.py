"""factory_boy factories for Guild and GuildMembership."""
import factory

from apps.guilds.models import Guild, GuildMembership, GuildRole

from .user_factory import UserFactory


class GuildFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Guild

    name = factory.Sequence(lambda n: f"Test Guild {n}")
    tag = factory.Sequence(lambda n: f"T{n:03d}"[:4].upper())
    description = "A test guild."
    created_by = factory.SubFactory(UserFactory)
    is_recruiting = True


class GuildMembershipFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = GuildMembership

    user = factory.SubFactory(UserFactory)
    guild = factory.SubFactory(GuildFactory)
    role = GuildRole.MEMBER

    class Params:
        owner = factory.Trait(role=GuildRole.OWNER)
        officer = factory.Trait(role=GuildRole.OFFICER)
