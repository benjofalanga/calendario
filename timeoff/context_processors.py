from .utils import is_manager


def role_flags(request):
    return {
        "is_manager": is_manager(request.user),
    }
