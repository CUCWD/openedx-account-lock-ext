"""An email-login model to exercise real Django swappable-user support."""

from django.contrib.auth.models import AbstractUser
from django.db import models


class EmailUser(AbstractUser):
    """Use email as the unique login field with no username database field."""

    username = None
    email = models.EmailField(unique=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
