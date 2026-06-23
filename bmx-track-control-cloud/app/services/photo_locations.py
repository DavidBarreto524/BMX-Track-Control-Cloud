from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.models import Area, MapHotspot, Photo
from app.services.map_hotspots import list_map_hotspots


def ensure_photo_hotspot_column(engine: Engine) -> None:
    inspector = inspect(engine)
    if "photos" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("photos")}
    if "hotspot_label" in columns:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE photos ADD COLUMN hotspot_label VARCHAR(10)"))


def hotspots_for_area_code(db: Session, area_code: str) -> list[MapHotspot]:
    normalized = area_code.strip().upper()
    return [
        hotspot
        for hotspot in list_map_hotspots(db)
        if hotspot.area_code.upper() == normalized
    ]


def hotspot_lookup_by_label(db: Session) -> dict[str, MapHotspot]:
    return {hotspot.label.upper(): hotspot for hotspot in list_map_hotspots(db)}


def format_photo_location(hotspot_label: str | None, description: str | None = None) -> str:
    if not hotspot_label:
        return ""
    label = hotspot_label.strip()
    if description and description.strip():
        return f"{label} — {description.strip()}"
    return label


def resolve_hotspot_for_area(
    db: Session,
    area: Area,
    hotspot_label: str | None,
) -> str | None:
    area_hotspots = hotspots_for_area_code(db, area.code or "")
    if not area_hotspots:
        if hotspot_label and hotspot_label.strip():
            return hotspot_label.strip().upper()
        return None

    if len(area_hotspots) == 1:
        return area_hotspots[0].label

    normalized = (hotspot_label or "").strip().upper()
    if not normalized:
        raise ValueError("Selecciona el punto del plano (A1, A2, Peralte 1…).")

    valid_labels = {hotspot.label.upper() for hotspot in area_hotspots}
    if normalized not in valid_labels:
        raise ValueError("El punto seleccionado no pertenece a esta área.")

    for hotspot in area_hotspots:
        if hotspot.label.upper() == normalized:
            return hotspot.label

    return normalized


def photo_location_display(photo: Photo, hotspots_by_label: dict[str, MapHotspot]) -> str:
    if not photo.hotspot_label:
        return ""
    hotspot = hotspots_by_label.get(photo.hotspot_label.upper())
    description = hotspot.description if hotspot else None
    display_label = hotspot.label if hotspot else photo.hotspot_label
    return format_photo_location(display_label, description)


def photo_report_label(
    photo: Photo,
    area: Area | None,
    hotspots_by_label: dict[str, MapHotspot],
) -> str:
    location = photo_location_display(photo, hotspots_by_label)
    if location:
        if area and area.code:
            return f"{location} · Área {area.code}"
        return location
    if area and area.code:
        return f"Área {area.code} — {area.name}"
    if area:
        return area.name
    return f"Área #{photo.area_id}"
