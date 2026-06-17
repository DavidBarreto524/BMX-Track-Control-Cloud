from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.security import has_permission
from app.services.users import SESSION_USER_ID_KEY, get_user_by_id


class LoginRedirect(Exception):
    pass


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get(SESSION_USER_ID_KEY)
    if not user_id:
        return None
    return get_user_by_id(db, user_id)


def require_web_user(
    request: Request,
    db: Session = Depends(get_db),
    permission: str | None = None,
) -> User:
    user = get_optional_user(request, db)
    if not user:
        raise LoginRedirect()

    if permission and not has_permission(user.role, permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para esta acción.",
        )

    return user


def require_api_user(
    request: Request,
    db: Session = Depends(get_db),
    permission: str | None = None,
) -> User:
    user = get_optional_user(request, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Debes iniciar sesión para usar la API.",
        )

    if permission and not has_permission(user.role, permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para esta acción.",
        )

    return user


def WebAuth(permission: str | None = None):
    def dependency(request: Request, db: Session = Depends(get_db)) -> User:
        return require_web_user(request, db, permission)

    return Depends(dependency)


def ApiAuth(permission: str | None = None):
    def dependency(request: Request, db: Session = Depends(get_db)) -> User:
        return require_api_user(request, db, permission)

    return Depends(dependency)
