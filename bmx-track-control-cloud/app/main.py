from contextlib import asynccontextmanager
from datetime import datetime
import json
from pathlib import Path
from typing import Annotated

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.database import Base, SessionLocal, engine, get_db
from app.dependencies.auth import ApiAuth, LoginRedirect, WebAuth, get_optional_user
from app.models import Alert, Area, Photo, User
from app.schemas import (
    AlertRead,
    AreaCreate,
    AreaRead,
    MapHotspotSave,
    PhotoNotesUpdate,
    PhotoRead,
    ReportGenerateRequest,
)
from app.services.alerts import evaluate_upload_alerts, resolve_open_alerts_for_area
from app.services.areas import ensure_area_code_column, ensure_track_areas
from app.services.security import has_permission
from app.services.storage import delete_stored_photo, store_photo
from app.services.pdf_report import ReportPhotoEntry, build_photos_pdf, resolve_photo_image_path
from app.services.map_hotspots import (
    TRACK_MAP_IMAGE,
    build_track_hotspots,
    ensure_map_hotspots,
    list_map_hotspots,
    replace_map_hotspots,
    reset_map_hotspots_to_defaults,
)
from app.services.users import SESSION_USER_ID_KEY, authenticate_user, ensure_bootstrap_users
from app.services.timezone import format_datetime as format_datetime_colombia
from app.services.timezone import format_filename_timestamp
from app.services.timezone import utc_now

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals["has_permission"] = has_permission


def _format_datetime(value: datetime | None) -> str:
    return format_datetime_colombia(value)


templates.env.filters["format_datetime"] = _format_datetime
scheduler = AsyncIOScheduler()

static_dir = BASE_DIR / "static"
uploads_dir = Path(settings.local_upload_dir)
uploads_dir.mkdir(parents=True, exist_ok=True)


def _upload_status(last_uploaded_at: datetime | None, interval_minutes: int) -> str:
    if last_uploaded_at is None:
        return "Sin fotos"
    diff_minutes = (utc_now() - last_uploaded_at).total_seconds() / 60
    return "Al día" if diff_minutes <= interval_minutes else "Atrasada"


def _scan_and_create_alerts() -> None:
    db = SessionLocal()
    try:
        evaluate_upload_alerts(db)
    finally:
        db.close()


def _to_area_read(area: Area, last_uploaded_at: datetime | None) -> AreaRead:
    return AreaRead(
        id=area.id,
        code=area.code,
        name=area.name,
        description=area.description,
        expected_upload_interval_minutes=area.expected_upload_interval_minutes,
        created_at=area.created_at,
        last_uploaded_at=last_uploaded_at,
        upload_status=_upload_status(last_uploaded_at, area.expected_upload_interval_minutes),
    )


def _area_dict(area: Area, last_uploaded_at: datetime | None) -> dict:
    return {
        "id": area.id,
        "code": area.code,
        "name": area.name,
        "description": area.description,
        "expected_upload_interval_minutes": area.expected_upload_interval_minutes,
        "last_uploaded_at": last_uploaded_at,
        "upload_status": _upload_status(last_uploaded_at, area.expected_upload_interval_minutes),
    }


def _status_css_class(upload_status: str) -> str:
    if upload_status == "Al día":
        return "zone-ok"
    if upload_status == "Atrasada":
        return "zone-late"
    return "zone-empty"


def _fetch_open_alerts(db: Session, user: User | None) -> list[Alert]:
    if not user or not has_permission(user.role, "view_alerts"):
        return []
    return (
        db.query(Alert)
        .options(joinedload(Alert.area))
        .filter(Alert.resolved.is_(False))
        .order_by(Alert.created_at.desc())
        .all()
    )


def _page_context(
    request: Request,
    db: Session,
    current_user: User | None = None,
    **extra,
) -> dict:
    context = {
        "request": request,
        "app_name": settings.app_name,
        "current_user": current_user,
        "open_alerts": _fetch_open_alerts(db, current_user),
    }
    context.update(extra)
    return context


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_area_code_column(engine)

    db = SessionLocal()
    try:
        ensure_bootstrap_users(db)
        ensure_track_areas(db)
        ensure_map_hotspots(db)
    finally:
        db.close()

    if settings.enable_scheduler and not scheduler.running:
        scheduler.add_job(
            _scan_and_create_alerts,
            trigger="interval",
            minutes=settings.upload_check_interval_minutes,
            id="scan-upload-alerts",
            replace_existing=True,
        )
        scheduler.start()

    yield

    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


@app.exception_handler(LoginRedirect)
async def login_redirect_handler(_: Request, __: LoginRedirect):
    return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db)):
    current_user = get_optional_user(request, db)
    if current_user:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "app_name": settings.app_name, "error": None},
    )


@app.post("/login")
def login_submit(
    request: Request,
    username: Annotated[str, Form(...)],
    password: Annotated[str, Form(...)],
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, username.strip(), password)
    if not user:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "app_name": settings.app_name,
                "error": "Usuario o contraseña incorrectos.",
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    request.session[SESSION_USER_ID_KEY] = user.id
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/logout")
def logout(request: Request, _: User = WebAuth("access_dashboard")):
    request.session.clear()
    return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db), current_user: User = WebAuth("access_dashboard")):
    areas_with_last_upload = (
        db.query(Area, func.max(Photo.uploaded_at).label("last_uploaded_at"))
        .outerjoin(Photo, Photo.area_id == Area.id)
        .group_by(Area.id)
        .order_by(Area.name.asc())
        .all()
    )
    areas_data = []
    areas_by_code: dict[str, dict] = {}
    for area, last_uploaded_at in areas_with_last_upload:
        area_info = _area_dict(area, last_uploaded_at)
        areas_data.append(area_info)
        if area.code:
            areas_by_code[area.code.upper()] = area_info

    track_hotspots = build_track_hotspots(db, areas_by_code)

    return templates.TemplateResponse(
        "index.html",
        _page_context(
            request,
            db,
            current_user,
            areas=areas_data,
            track_hotspots=track_hotspots,
            track_map_image=TRACK_MAP_IMAGE,
            default_interval=settings.default_photo_interval_minutes,
        ),
    )


@app.get("/areas/{area_code}", response_class=HTMLResponse)
def area_detail(
    area_code: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = WebAuth("access_dashboard"),
):
    normalized_code = area_code.strip().upper()
    area = db.query(Area).filter(Area.code == normalized_code).first()
    if not area:
        raise HTTPException(status_code=404, detail="Área no encontrada.")

    last_uploaded_at = (
        db.query(func.max(Photo.uploaded_at))
        .filter(Photo.area_id == area.id)
        .scalar()
    )
    photos = (
        db.query(Photo)
        .filter(Photo.area_id == area.id)
        .order_by(Photo.uploaded_at.desc())
        .all()
    )

    area_info = _area_dict(area, last_uploaded_at)

    return templates.TemplateResponse(
        "area_detail.html",
        _page_context(
            request,
            db,
            current_user,
            area=area_info,
            photos=photos,
        ),
    )


@app.get("/admin/mapa-calibracion", response_class=HTMLResponse)
def map_calibration_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = WebAuth("calibrate_map"),
):
    hotspots = list_map_hotspots(db)
    hotspots_payload = [
        {
            "label": item.label,
            "area_code": item.area_code,
            "top": item.top,
            "left": item.left,
            "width": item.width,
            "height": item.height,
            "description": item.description,
            "sort_order": item.sort_order,
        }
        for item in hotspots
    ]

    return templates.TemplateResponse(
        "map_calibration.html",
        _page_context(
            request,
            db,
            current_user,
            track_map_image=TRACK_MAP_IMAGE,
            hotspots_json=json.dumps(hotspots_payload),
        ),
    )


@app.post("/admin/mapa-calibracion")
def save_map_calibration(
    payload: MapHotspotSave,
    db: Session = Depends(get_db),
    _: User = ApiAuth("calibrate_map"),
):
    labels = [item.label.strip().upper() for item in payload.hotspots]
    if len(labels) != len(set(labels)):
        raise HTTPException(status_code=400, detail="Cada etiqueta debe ser única (A1, A2, L1…).")

    replace_map_hotspots(db, [item.model_dump() for item in payload.hotspots])
    saved = list_map_hotspots(db)
    return [
        {
            "label": item.label,
            "area_code": item.area_code,
            "top": item.top,
            "left": item.left,
            "width": item.width,
            "height": item.height,
            "description": item.description,
            "sort_order": item.sort_order,
        }
        for item in saved
    ]


@app.post("/admin/mapa-calibracion/restaurar")
def restore_map_calibration(
    db: Session = Depends(get_db),
    _: User = ApiAuth("calibrate_map"),
):
    reset_map_hotspots_to_defaults(db)
    saved = list_map_hotspots(db)
    return [
        {
            "label": item.label,
            "area_code": item.area_code,
            "top": item.top,
            "left": item.left,
            "width": item.width,
            "height": item.height,
            "description": item.description,
            "sort_order": item.sort_order,
        }
        for item in saved
    ]


@app.post("/areas")
def create_area_from_form(
    name: Annotated[str, Form(...)],
    code: Annotated[str | None, Form()] = None,
    description: Annotated[str | None, Form()] = None,
    expected_upload_interval_minutes: Annotated[int | None, Form()] = None,
    db: Session = Depends(get_db),
    _: User = WebAuth("manage_areas"),
):
    payload = AreaCreate(
        name=name,
        code=code.strip().upper() if code else None,
        description=description,
        expected_upload_interval_minutes=expected_upload_interval_minutes,
    )
    interval = payload.expected_upload_interval_minutes or settings.default_photo_interval_minutes
    area = Area(
        code=payload.code.strip().upper() if payload.code else None,
        name=payload.name,
        description=payload.description,
        expected_upload_interval_minutes=interval,
    )
    db.add(area)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="El área ya existe.") from exc

    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


def _get_photo_or_404(db: Session, photo_id: int, area_id: int | None = None) -> Photo:
    query = db.query(Photo).filter(Photo.id == photo_id)
    if area_id is not None:
        query = query.filter(Photo.area_id == area_id)
    photo = query.first()
    if not photo:
        raise HTTPException(status_code=404, detail="Foto no encontrada.")
    return photo


@app.post("/areas/{area_code}/photos/{photo_id}/delete")
def delete_photo_from_form(
    area_code: str,
    photo_id: int,
    db: Session = Depends(get_db),
    _: User = WebAuth("delete_photos"),
):
    normalized_code = area_code.strip().upper()
    area = db.query(Area).filter(Area.code == normalized_code).first()
    if not area:
        raise HTTPException(status_code=404, detail="Área no encontrada.")

    photo = _get_photo_or_404(db, photo_id, area_id=area.id)
    delete_stored_photo(photo.image_url)
    db.delete(photo)
    db.commit()
    return RedirectResponse(url=f"/areas/{normalized_code}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/areas/{area_id}/upload")
async def upload_photo_from_form(
    area_id: int,
    file: UploadFile = File(...),
    notes: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
    _: User = WebAuth("upload_photos"),
):
    area = db.query(Area).filter(Area.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Área no encontrada.")

    try:
        image_url = await store_photo(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="No se pudo subir la imagen.") from exc

    db.add(Photo(area_id=area_id, image_url=image_url, notes=notes))
    resolve_open_alerts_for_area(db, area_id)
    db.commit()

    redirect_url = f"/areas/{area.code}" if area.code else "/"
    return RedirectResponse(redirect_url, status_code=status.HTTP_303_SEE_OTHER)


@app.post("/api/areas", response_model=AreaRead, status_code=status.HTTP_201_CREATED)
def create_area(
    payload: AreaCreate,
    db: Session = Depends(get_db),
    _: User = ApiAuth("manage_areas"),
):
    interval = payload.expected_upload_interval_minutes or settings.default_photo_interval_minutes
    area = Area(
        code=payload.code.strip().upper() if payload.code else None,
        name=payload.name,
        description=payload.description,
        expected_upload_interval_minutes=interval,
    )
    db.add(area)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="El área ya existe.") from exc

    db.refresh(area)
    return _to_area_read(area, None)


@app.get("/api/areas", response_model=list[AreaRead])
def list_areas(db: Session = Depends(get_db), _: User = ApiAuth("use_api")):
    rows = (
        db.query(Area, func.max(Photo.uploaded_at).label("last_uploaded_at"))
        .outerjoin(Photo, Photo.area_id == Area.id)
        .group_by(Area.id)
        .order_by(Area.name.asc())
        .all()
    )
    response: list[AreaRead] = []
    for area, last_uploaded_at in rows:
        response.append(_to_area_read(area, last_uploaded_at))
    return response


@app.post("/api/areas/{area_id}/photos", response_model=PhotoRead, status_code=status.HTTP_201_CREATED)
async def upload_photo_api(
    area_id: int,
    file: UploadFile = File(...),
    notes: Annotated[str | None, Form()] = None,
    db: Session = Depends(get_db),
    _: User = ApiAuth("upload_photos"),
):
    area = db.query(Area).filter(Area.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Área no encontrada.")

    try:
        image_url = await store_photo(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="No se pudo subir la imagen.") from exc

    photo = Photo(area_id=area_id, image_url=image_url, notes=notes)
    db.add(photo)
    resolve_open_alerts_for_area(db, area_id)
    db.commit()
    db.refresh(photo)
    return photo


@app.get("/api/areas/{area_id}/photos", response_model=list[PhotoRead])
def list_area_photos(
    area_id: int,
    db: Session = Depends(get_db),
    _: User = ApiAuth("use_api"),
):
    area = db.query(Area).filter(Area.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Área no encontrada.")

    return (
        db.query(Photo)
        .filter(Photo.area_id == area_id)
        .order_by(Photo.uploaded_at.desc())
        .all()
    )


@app.delete("/api/areas/{area_id}/photos/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_photo_api(
    area_id: int,
    photo_id: int,
    db: Session = Depends(get_db),
    _: User = ApiAuth("delete_photos"),
):
    area = db.query(Area).filter(Area.id == area_id).first()
    if not area:
        raise HTTPException(status_code=404, detail="Área no encontrada.")

    photo = _get_photo_or_404(db, photo_id, area_id=area_id)
    delete_stored_photo(photo.image_url)
    db.delete(photo)
    db.commit()


@app.get("/api/alerts", response_model=list[AlertRead])
def list_alerts(
    only_open: bool = True,
    db: Session = Depends(get_db),
    _: User = ApiAuth("view_alerts"),
):
    query = db.query(Alert)
    if only_open:
        query = query.filter(Alert.resolved.is_(False))
    return query.order_by(Alert.created_at.desc()).all()


@app.get("/reportes", response_class=HTMLResponse)
def report_builder_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = WebAuth("generate_reports"),
):
    photos = (
        db.query(Photo)
        .options(joinedload(Photo.area))
        .order_by(Photo.uploaded_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "report_builder.html",
        _page_context(request, db, current_user, photos=photos),
    )


@app.post("/reportes/pdf")
def generate_report_pdf(
    payload: ReportGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = WebAuth("generate_reports"),
):
    photo_ids = [item.photo_id for item in payload.photos]
    rows = (
        db.query(Photo)
        .options(joinedload(Photo.area))
        .filter(Photo.id.in_(photo_ids))
        .all()
    )
    photos_by_id = {photo.id: photo for photo in rows}
    if len(photos_by_id) != len(set(photo_ids)):
        raise HTTPException(status_code=404, detail="Alguna foto seleccionada no existe.")

    notes_by_id = {item.photo_id: (item.notes or "").strip() or None for item in payload.photos}

    if payload.save_notes:
        for item in payload.photos:
            photo = photos_by_id[item.photo_id]
            photo.notes = notes_by_id[item.photo_id]
        db.commit()

    entries: list[ReportPhotoEntry] = []
    temp_files: list[Path] = []
    try:
        for item in payload.photos:
            photo = photos_by_id[item.photo_id]
            try:
                image_path = resolve_photo_image_path(photo.image_url)
            except (ValueError, OSError) as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"No se pudo cargar la imagen de la foto #{photo.id}.",
                ) from exc

            if not photo.image_url.startswith("/uploads/"):
                temp_files.append(image_path)

            area = photo.area
            if area and area.code:
                area_label = f"Área {area.code} — {area.name}"
            elif area:
                area_label = area.name
            else:
                area_label = f"Área #{photo.area_id}"

            entries.append(
                ReportPhotoEntry(
                    area_label=area_label,
                    uploaded_at=photo.uploaded_at,
                    notes=notes_by_id[item.photo_id],
                    image_path=image_path,
                )
            )

        pdf_bytes = build_photos_pdf(payload.title.strip(), entries, current_user.username)
    finally:
        for path in temp_files:
            path.unlink(missing_ok=True)

    filename = f"reporte-bmx-{format_filename_timestamp()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.patch("/api/photos/{photo_id}/notes", response_model=PhotoRead)
def update_photo_notes(
    photo_id: int,
    payload: PhotoNotesUpdate,
    db: Session = Depends(get_db),
    _: User = ApiAuth("edit_photo_notes"),
):
    photo = _get_photo_or_404(db, photo_id)
    photo.notes = payload.notes.strip() if payload.notes else None
    db.commit()
    db.refresh(photo)
    return photo


@app.get("/health")
def health_check():
    return {"status": "ok", "service": settings.app_name}
