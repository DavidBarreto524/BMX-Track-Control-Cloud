import asyncio
import os
import sys
from io import BytesIO
from pathlib import Path

import httpx
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


def test_cloudinary_public_id_strips_version_and_extension():
    url = (
        "https://res.cloudinary.com/degoyxevs/image/upload/"
        "v1782336213/bmx-track-control/bmx_abc123.jpg"
    )
    assert storage.cloudinary_public_id(url) == "bmx-track-control/bmx_abc123"


def test_cloudinary_delivery_candidates_include_versionless_url(monkeypatch):
    monkeypatch.setattr(storage.settings, "cloudinary_cloud_name", "degoyxevs")
    monkeypatch.setattr(storage.settings, "cloudinary_api_key", "key")
    monkeypatch.setattr(storage.settings, "cloudinary_api_secret", "secret")

    def fake_resource(public_id, resource_type="image"):
        return {
            "secure_url": (
                "https://res.cloudinary.com/degoyxevs/image/upload/"
                f"{public_id}.jpg"
            )
        }

    monkeypatch.setattr(storage.cloudinary.api, "resource", fake_resource)

    stored_url = (
        "https://res.cloudinary.com/degoyxevs/image/upload/"
        "v1782336213/bmx-track-control/bmx_abc123.jpg"
    )
    candidates = storage._cloudinary_delivery_candidates(stored_url)
    assert stored_url in candidates
    assert any("v1782336213" not in url for url in candidates)
    assert len(candidates) >= 2


def test_download_image_for_report_retries_next_cloudinary_url(monkeypatch):
    monkeypatch.setattr(storage.settings, "cloudinary_cloud_name", "degoyxevs")
    monkeypatch.setattr(storage.settings, "cloudinary_api_key", "key")
    monkeypatch.setattr(storage.settings, "cloudinary_api_secret", "secret")
    monkeypatch.setattr(
        storage.cloudinary.api,
        "resource",
        lambda public_id, resource_type="image": {"secure_url": "https://cdn.example/ok.jpg"},
    )

    calls: list[str] = []

    def fake_download(url: str) -> Path:
        calls.append(url)
        if len(calls) == 1:
            response = httpx.Response(404, request=httpx.Request("GET", url))
            raise httpx.HTTPStatusError("missing", request=response.request, response=response)
        path = Path("tests/uploads/report-temp.jpg")
        path.write_bytes(b"jpeg")
        return path

    monkeypatch.setattr(storage, "_http_download_to_temp", fake_download)

    stored_url = (
        "https://res.cloudinary.com/degoyxevs/image/upload/"
        "v1782336213/bmx-track-control/bmx_abc123.jpg"
    )
    result = storage.download_image_for_report(stored_url)
    assert result.exists()
    assert len(calls) >= 2
    result.unlink(missing_ok=True)


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
