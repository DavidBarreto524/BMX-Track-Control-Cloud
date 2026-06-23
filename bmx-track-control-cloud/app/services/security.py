import bcrypt

from app.config import settings

_ADMIN_PERMISSIONS = frozenset(
    {
        "access_dashboard",
        "manage_areas",
        "calibrate_map",
        "upload_photos",
        "edit_photo_notes",
        "generate_reports",
        "view_alerts",
        "use_api",
    }
)
ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "admin": _ADMIN_PERMISSIONS,
    "supervisor": _ADMIN_PERMISSIONS,
    "viewer": frozenset(
        {
            "access_dashboard",
            "view_alerts",
        }
    ),
}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def has_permission(role: str, permission: str) -> bool:
    normalized_role = (role or "").lower()
    return permission in ROLE_PERMISSIONS.get(normalized_role, set())


def can_delete_photos(username: str | None) -> bool:
    normalized = (username or "").strip().lower()
    if not normalized:
        return False
    allowed_usernames = [settings.admin_username]
    if settings.jimmy_username:
        allowed_usernames.append(settings.jimmy_username)
    return normalized in {name.strip().lower() for name in allowed_usernames if name}

