from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Area
from app.services.track_areas import TRACK_AREAS


def ensure_area_code_column(engine: Engine) -> None:
    inspector = inspect(engine)
    if "areas" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("areas")}
    if "code" in columns:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE areas ADD COLUMN code VARCHAR(10)"))
        connection.execute(
            text("CREATE UNIQUE INDEX IF NOT EXISTS ix_areas_code ON areas (code)")
        )


def ensure_track_areas(db: Session) -> None:
    for track_area in TRACK_AREAS:
        area = db.query(Area).filter(Area.code == track_area["code"]).first()
        if area:
            continue

        existing_by_name = db.query(Area).filter(Area.name == track_area["name"]).first()
        if existing_by_name:
            existing_by_name.code = track_area["code"]
            if not existing_by_name.description:
                existing_by_name.description = track_area["description"]
            continue

        db.add(
            Area(
                code=track_area["code"],
                name=track_area["name"],
                description=track_area["description"],
                expected_upload_interval_minutes=settings.default_photo_interval_minutes,
            )
        )

    db.commit()
