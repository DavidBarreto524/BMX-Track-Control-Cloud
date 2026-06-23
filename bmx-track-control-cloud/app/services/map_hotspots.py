"""Marcadores del plano con etiquetas únicas (A1, A2, L1...) vinculadas al área logística."""

from sqlalchemy.orm import Session

from app.models import MapHotspot

TRACK_MAP_IMAGE = "/static/images/cancha.png"

DEFAULT_MAP_HOTSPOTS: list[dict[str, float | str | None]] = [
    {"label": "B1", "area_code": "B", "top": 18.3, "left": 55.8, "description": "Gradería"},
    {"label": "B2", "area_code": "B", "top": 18.7, "left": 19.2, "description": "Gradería"},
    {"label": "A1", "area_code": "A", "top": 18.9, "left": 70.7, "description": "Acceso edificio principal"},
    {"label": "A2", "area_code": "A", "top": 23.8, "left": 24.3, "description": "Pasillo frente a gradería"},
    {"label": "M", "area_code": "M", "top": 29.6, "left": 71.0, "description": "Oficina / premiación"},
    {"label": "C", "area_code": "C", "top": 25.6, "left": 76.3, "description": "Puerta principal"},
    {"label": "H", "area_code": "H", "top": 35.6, "left": 73.6, "description": "Control baños"},
    {"label": "D", "area_code": "D", "top": 20.0, "left": 81.5, "description": "Ingreso carpas"},
    {"label": "G", "area_code": "G", "top": 38.3, "left": 81.7, "description": "Cinta delimitante corrales"},
    {"label": "F", "area_code": "F", "top": 48.5, "left": 76.7, "description": "Llamado de mangas"},
    {"label": "I", "area_code": "I", "top": 59.2, "left": 75.3, "description": "Ingreso a pista"},
    {"label": "E", "area_code": "E", "top": 60.5, "left": 88.5, "description": "Entrada / salida mangas"},
    {"label": "Peralte 1", "area_code": "L", "top": 50.9, "left": 11.8, "description": "Curva izquierda superior"},
    {"label": "Peralte 2", "area_code": "L", "top": 85.8, "left": 14.9, "description": "Curva inferior izquierda"},
    {"label": "Peralte 3", "area_code": "L", "top": 68.5, "left": 69.9, "description": "Curva derecha central"},
    {"label": "K", "area_code": "K", "top": 95.0, "left": 53.0, "description": "Recta de llegada / patinador"},
    {"label": "J", "area_code": "J", "top": 84.9, "left": 78.0, "description": "Ingreso zona llegada"},
]

DEFAULT_HOTSPOT_WIDTH = 2.5
DEFAULT_HOTSPOT_HEIGHT = 4.9

LEGACY_L_HOTSPOT_RENAMES = {
    "L1": "Peralte 1",
    "L2": "Peralte 2",
    "L3": "Peralte 3",
}


def migrate_legacy_l_hotspot_labels(db: Session) -> None:
    from app.models import Photo

    for old_label, new_label in LEGACY_L_HOTSPOT_RENAMES.items():
        if db.query(MapHotspot).filter(MapHotspot.label == new_label).first():
            for variant in (old_label, old_label.upper()):
                legacy = db.query(MapHotspot).filter(MapHotspot.label == variant).first()
                if legacy:
                    db.delete(legacy)
            db.query(Photo).filter(Photo.hotspot_label.in_([old_label, old_label.upper()])).update(
                {Photo.hotspot_label: new_label},
                synchronize_session=False,
            )
            continue

        for variant in (old_label, old_label.upper()):
            hotspot = db.query(MapHotspot).filter(MapHotspot.label == variant).first()
            if hotspot:
                hotspot.label = new_label
            db.query(Photo).filter(Photo.hotspot_label == variant).update(
                {Photo.hotspot_label: new_label},
                synchronize_session=False,
            )

    db.commit()


def reset_map_hotspots_to_defaults(db: Session) -> None:
    replace_map_hotspots(
        db,
        [
            {
                "label": item["label"],
                "area_code": item["area_code"],
                "top": item["top"],
                "left": item["left"],
                "width": DEFAULT_HOTSPOT_WIDTH,
                "height": DEFAULT_HOTSPOT_HEIGHT,
                "description": item.get("description"),
                "sort_order": index,
            }
            for index, item in enumerate(DEFAULT_MAP_HOTSPOTS)
        ],
    )


def ensure_map_hotspots(db: Session) -> None:
    for index, item in enumerate(DEFAULT_MAP_HOTSPOTS):
        label = str(item["label"])
        exists = db.query(MapHotspot).filter(MapHotspot.label == label).first()
        if exists:
            continue

        db.add(
            MapHotspot(
                label=label,
                area_code=str(item["area_code"]).upper(),
                top=float(item["top"]),
                left=float(item["left"]),
                width=DEFAULT_HOTSPOT_WIDTH,
                height=DEFAULT_HOTSPOT_HEIGHT,
                description=item.get("description"),
                sort_order=index,
            )
        )
    db.commit()


def list_map_hotspots(db: Session) -> list[MapHotspot]:
    return db.query(MapHotspot).order_by(MapHotspot.sort_order.asc(), MapHotspot.label.asc()).all()


def hotspot_to_dict(hotspot: MapHotspot, area: dict | None = None) -> dict:
    return {
        "id": hotspot.id,
        "label": hotspot.label,
        "area_code": hotspot.area_code,
        "top": hotspot.top,
        "left": hotspot.left,
        "width": hotspot.width,
        "height": hotspot.height,
        "description": hotspot.description,
        "area": area,
        "status_class": _status_from_area(area),
    }


def _status_from_area(area: dict | None) -> str:
    if not area:
        return "zone-missing"
    status = area.get("upload_status", "Sin fotos")
    if status == "Al día":
        return "zone-ok"
    if status == "Atrasada":
        return "zone-late"
    return "zone-empty"


def build_track_hotspots(db: Session, areas_by_code: dict[str, dict]) -> list[dict]:
    rows = list_map_hotspots(db)
    result: list[dict] = []
    for hotspot in rows:
        area = areas_by_code.get(hotspot.area_code.upper())
        result.append(hotspot_to_dict(hotspot, area))
    return result


def replace_map_hotspots(db: Session, payload: list[dict]) -> None:
    db.query(MapHotspot).delete()
    for index, item in enumerate(payload):
        db.add(
            MapHotspot(
                label=str(item["label"]).strip(),
                area_code=str(item["area_code"]).strip().upper(),
                top=float(item["top"]),
                left=float(item["left"]),
                width=float(item.get("width", DEFAULT_HOTSPOT_WIDTH)),
                height=float(item.get("height", DEFAULT_HOTSPOT_HEIGHT)),
                description=item.get("description") or None,
                sort_order=int(item.get("sort_order", index)),
            )
        )
    db.commit()
