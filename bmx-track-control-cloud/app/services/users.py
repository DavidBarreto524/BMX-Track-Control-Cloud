from sqlalchemy.orm import Session

from app.config import settings
from app.models import User
from app.services.security import hash_password, verify_password

SESSION_USER_ID_KEY = "user_id"


def ensure_user(db: Session, username: str, password: str, role: str = "viewer") -> None:
    existing = db.query(User).filter(User.username == username).first()
    if existing:
        return

    db.add(
        User(
            username=username,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
    )
    db.commit()


def ensure_default_admin(db: Session) -> None:
    ensure_user(db, settings.admin_username, settings.admin_password, "admin")


def ensure_bootstrap_users(db: Session) -> None:
    ensure_default_admin(db)
    if settings.jimmy_username and settings.jimmy_password:
        ensure_user(
            db,
            settings.jimmy_username,
            settings.jimmy_password,
            settings.jimmy_role,
        )


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = (
        db.query(User)
        .filter(User.username == username, User.is_active.is_(True))
        .first()
    )
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return (
        db.query(User)
        .filter(User.id == user_id, User.is_active.is_(True))
        .first()
    )
