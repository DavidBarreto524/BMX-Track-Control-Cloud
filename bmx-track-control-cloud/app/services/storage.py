import re
from pathlib import Path
from uuid import uuid4

import cloudinary
import cloudinary.uploader
from fastapi import UploadFile

from app.config import settings

_cloudinary_configured = False


def _cloudinary_enabled() -> bool:
    return bool(
        settings.cloudinary_cloud_name
        and settings.cloudinary_api_key
        and settings.cloudinary_api_secret
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


async def store_photo(file: UploadFile) -> str:
    payload = await file.read()
    if not payload:
        raise ValueError("El archivo de imagen está vacío.")

    suffix = Path(file.filename or "foto.jpg").suffix or ".jpg"
    safe_name = f"bmx_{uuid4().hex}{suffix}"

    if _cloudinary_enabled():
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
    if public_id and _cloudinary_enabled():
        _configure_cloudinary()
        cloudinary.uploader.destroy(public_id, resource_type="image")

