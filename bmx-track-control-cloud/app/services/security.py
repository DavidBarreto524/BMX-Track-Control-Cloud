import bcrypt

ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {
        "access_dashboard",
        "manage_areas",
        "calibrate_map",
        "upload_photos",
        "delete_photos",
        "edit_photo_notes",
        "generate_reports",
        "view_alerts",
        "use_api",
    },
    "supervisor": {
        "access_dashboard",
        "delete_photos",
        "edit_photo_notes",
        "generate_reports",
        "view_alerts",
        "use_api",
    },
    "viewer": {
        "access_dashboard",
        "view_alerts",
    },
}


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def has_permission(role: str, permission: str) -> bool:
    normalized_role = (role or "").lower()
    return permission in ROLE_PERMISSIONS.get(normalized_role, set())

