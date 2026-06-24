import logging
import re
from pathlib import Path
from uuid import uuid4

import cloudinary
import cloudinary.uploader
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Photo

logger = logging.getLogger(__name__)
_cloudinary_configured = False


def is_production_deployment() -> bool:
    database_url = settings.database_url.lower()
    return "postgresql" in database_url or database_url.startswith("postgres:")


def cloudinary_enabled() -> bool:
    return bool(
        settings.cloudinary_cloud_name
        and settings.cloudinary_api_key
        and settings.cloudinary_api_secret
    )


def photo_storage_status() -> dict[str, str | bool | None]:
    production = is_production_deployment()
    cloudinary = cloudinary_enabled()
    persistent = (not production) or cloudinary
    warning = None
    if production and not cloudinary:
        warning = (
            "Almacenamiento temporal: configura Cloudinary en Render "
            "(CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET). "
            "Sin eso las fotos se pierden al reiniciar el servidor."
        )
    return {
        "production": production,
        "cloudinary_configured": cloudinary,
        "persistent_storage": persistent,
        "warning": warning,
    }


def count_ephemeral_photo_records(db: Session) -> int:
    return (
        db.query(Photo)
        .filter(Photo.image_url.like("/uploads/%"))
        .count()
    )


def _configure_cloudinary() -> None:
    global _cloudinary_configured
    if _cloudinary_configured:
        return
    cloudinary.config(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )
    _cloudinary_configured = True


def _ensure_upload_storage_ready() -> None:
    if is_production_deployment() and not cloudinary_enabled():
        raise ValueError(
            "En producción las fotos deben guardarse en Cloudinary. "
            "Configura CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY y "
            "CLOUDINARY_API_SECRET en las variables de entorno de Render."
        )


async def store_photo(file: UploadFile) -> str:
    _ensure_upload_storage_ready()

    payload = await file.read()
    if not payload:
        raise ValueError("El archivo de imagen está vacío.")

    suffix = Path(file.filename or "foto.jpg").suffix or ".jpg"
    safe_name = f"bmx_{uuid4().hex}{suffix}"

    if cloudinary_enabled():
        _configure_cloudinary()
        upload_kwargs = {
            "public_id": f"bmx-track-control/{Path(safe_name).stem}",
            "resource_type": "image",
            "overwrite": False,
        }
        if settings.cloudinary_upload_preset:
            upload_kwargs["upload_preset"] = settings.cloudinary_upload_preset

        result = cloudinary.uploader.upload(payload, **upload_kwargs)
        return result["secure_url"]

    local_dir = Path(settings.local_upload_dir)
    local_dir.mkdir(parents=True, exist_ok=True)
    destination = local_dir / safe_name
    destination.write_bytes(payload)
    return f"/uploads/{safe_name}"


def _cloudinary_public_id(image_url: str) -> str | None:
    if "res.cloudinary.com" not in image_url:
        return None
    match = re.search(r"/upload/(?:v\d+/)?(.+)$", image_url)
    if not match:
        return None
    public_id = match.group(1)
    if "." in public_id.rsplit("/", 1)[-1]:
        public_id = public_id.rsplit(".", 1)[0]
    return public_id


def delete_stored_photo(image_url: str) -> None:
    if image_url.startswith("/uploads/"):
        filename = image_url.removeprefix("/uploads/").lstrip("/")
        path = Path(settings.local_upload_dir) / filename
        if path.is_file():
            path.unlink()
        return

    public_id = _cloudinary_public_id(image_url)
    if public_id and cloudinary_enabled():
        _configure_cloudinary()
        cloudinary.uploader.destroy(public_id, resource_type="image")


def log_storage_status_on_startup() -> None:
    status = photo_storage_status()
    if status["warning"]:
        logger.warning(str(status["warning"]))
    elif status["production"] and status["cloudinary_configured"]:
        logger.info("Almacenamiento de fotos: Cloudinary activo en producción.")
