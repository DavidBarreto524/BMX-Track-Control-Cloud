import asyncio
import os
import sys
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_bmx.db")
os.environ.setdefault("SESSION_SECRET_KEY", "test-secret-key")

from app.services import storage  # noqa: E402


def test_local_upload_allowed_with_sqlite(monkeypatch):
    monkeypatch.setattr(storage.settings, "database_url", "sqlite:///./test.db")
    monkeypatch.setattr(storage.settings, "cloudinary_cloud_name", None)
    monkeypatch.setattr(storage.settings, "cloudinary_api_key", None)
    monkeypatch.setattr(storage.settings, "cloudinary_api_secret", None)

    upload = UploadFile(filename="foto.jpg", file=BytesIO(b"fake-image"))
    image_url = asyncio.run(storage.store_photo(upload))
    assert image_url.startswith("/uploads/")


def test_production_requires_cloudinary(monkeypatch):
    monkeypatch.setattr(
        storage.settings,
        "database_url",
        "postgresql://user:pass@host/db",
    )
    monkeypatch.setattr(storage.settings, "cloudinary_cloud_name", None)
    monkeypatch.setattr(storage.settings, "cloudinary_api_key", None)
    monkeypatch.setattr(storage.settings, "cloudinary_api_secret", None)

    upload = UploadFile(filename="foto.jpg", file=BytesIO(b"fake-image"))
    with pytest.raises(ValueError, match="Cloudinary"):
        asyncio.run(storage.store_photo(upload))


def test_photo_storage_status_degraded_in_production_without_cloudinary(monkeypatch):
    monkeypatch.setattr(
        storage.settings,
        "database_url",
        "postgresql://user:pass@host/db",
    )
    monkeypatch.setattr(storage.settings, "cloudinary_cloud_name", None)

    status = storage.photo_storage_status()
    assert status["production"] is True
    assert status["cloudinary_configured"] is False
    assert status["persistent_storage"] is False
    assert status["warning"]
