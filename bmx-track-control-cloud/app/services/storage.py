import logging
import re
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse
from uuid import uuid4

import cloudinary
import cloudinary.api
import cloudinary.uploader
import cloudinary.utils
import httpx
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
        public_id = result.get("public_id")
        if public_id:
            delivery_url, _ = cloudinary.utils.cloudinary_url(
                public_id,
                resource_type="image",
                secure=True,
                format=result.get("format") or "jpg",
            )
            return delivery_url
        return result["secure_url"]

    local_dir = Path(settings.local_upload_dir)
    local_dir.mkdir(parents=True, exist_ok=True)
    destination = local_dir / safe_name
    destination.write_bytes(payload)
    return f"/uploads/{safe_name}"


def cloudinary_public_id(image_url: str) -> str | None:
    if "res.cloudinary.com" not in image_url:
        return None
    match = re.search(r"/upload/(?:v\d+/)?(.+)$", image_url)
    if not match:
        return None
    public_id = match.group(1)
    if "." in public_id.rsplit("/", 1)[-1]:
        public_id = public_id.rsplit(".", 1)[0]
    return public_id


def _cloudinary_delivery_candidates(image_url: str) -> list[str]:
    public_id = cloudinary_public_id(image_url)
    if not public_id or not cloudinary_enabled():
        return [image_url]

    _configure_cloudinary()
    candidates: list[str] = []

    def add(url: str | None) -> None:
        if url and url not in candidates:
            candidates.append(url)

    add(image_url)

    versionless_url, _ = cloudinary.utils.cloudinary_url(
        public_id,
        resource_type="image",
        secure=True,
    )
    add(versionless_url)

    try:
        resource = cloudinary.api.resource(public_id, resource_type="image")
        add(resource.get("secure_url"))
        add(resource.get("url"))
    except Exception:
        logger.debug("No se encontró el recurso %s en Cloudinary.", public_id)

    return candidates or [image_url]


def _http_download_to_temp(image_url: str) -> Path:
    suffix = Path(urlparse(image_url).path).suffix or ".jpg"
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.get(image_url)
        response.raise_for_status()
        with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(response.content)
            return Path(tmp.name)


def download_image_for_report(image_url: str) -> Path:
    if image_url.startswith("/uploads/"):
        filename = image_url.removeprefix("/uploads/").lstrip("/")
        path = Path(settings.local_upload_dir) / filename
        if path.is_file():
            return path
        raise ValueError(
            "La imagen local ya no está en el servidor. Vuelve a subir la foto o exclúyela del reporte."
        )

    if not image_url.startswith("http://") and not image_url.startswith("https://"):
        raise ValueError(f"No se pudo cargar la imagen: {image_url}")

    candidates = (
        _cloudinary_delivery_candidates(image_url)
        if "res.cloudinary.com" in image_url
        else [image_url]
    )

    last_error: Exception | None = None
    for candidate_url in candidates:
        try:
            return _http_download_to_temp(candidate_url)
        except httpx.HTTPStatusError as exc:
            last_error = exc
            logger.warning(
                "Descarga fallida (%s) para %s",
                exc.response.status_code,
                candidate_url,
            )

    raise ValueError(
        "La imagen ya no está disponible en Cloudinary. "
        "Vuelve a subir la foto o exclúyela del reporte."
    ) from last_error


def _cloudinary_public_id(image_url: str) -> str | None:
    return cloudinary_public_id(image_url)


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
