from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import Alert, Area, Photo
from app.services.timezone import utc_now


def evaluate_upload_alerts(db: Session) -> int:
    areas = db.query(Area).all()
    now = utc_now()
    created_alerts = 0

    for area in areas:
        latest_photo = (
            db.query(Photo)
            .filter(Photo.area_id == area.id)
            .order_by(Photo.uploaded_at.desc())
            .first()
        )

        if latest_photo is None:
            overdue = now > (area.created_at + timedelta(minutes=area.expected_upload_interval_minutes))
        else:
            deadline = latest_photo.uploaded_at + timedelta(minutes=area.expected_upload_interval_minutes)
            overdue = now > deadline

        if not overdue:
            continue

        already_open = (
            db.query(Alert)
            .filter(Alert.area_id == area.id, Alert.resolved.is_(False))
            .order_by(Alert.created_at.desc())
            .first()
        )
        if already_open:
            continue

        db.add(
            Alert(
                area_id=area.id,
                message=f"El área '{area.name}' no tiene foto dentro del intervalo esperado.",
                resolved=False,
            )
        )
        created_alerts += 1

    if created_alerts:
        db.commit()

    return created_alerts


def resolve_open_alerts_for_area(db: Session, area_id: int) -> None:
    db.query(Alert).filter(Alert.area_id == area_id, Alert.resolved.is_(False)).update(
        {Alert.resolved: True},
        synchronize_session=False,
    )

