from django.contrib.auth.models import User


def is_manager(user: User) -> bool:
    if not user.is_authenticated:
        return False

    if user.is_superuser or user.is_staff:
        return True

    profile = getattr(user, "profile", None)
    return bool(profile and profile.role == "manager")
