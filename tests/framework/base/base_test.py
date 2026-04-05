"""BaseTest — all test classes must inherit from this."""
import pytest


@pytest.mark.django_db
class BaseTest:
    """
    Base class for every test in the project.

    Marks the class for database access and provides hooks for
    subclasses to reference shared fixtures via self.* assignments
    in overridden setup methods.
    """
