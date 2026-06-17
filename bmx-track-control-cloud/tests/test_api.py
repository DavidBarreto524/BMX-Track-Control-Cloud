import os
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test_bmx.db"
os.environ["ENABLE_SCHEDULER"] = "false"
os.environ["LOCAL_UPLOAD_DIR"] = "tests/uploads"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "admin123"
os.environ["SESSION_SECRET_KEY"] = "test-secret-key"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.areas import ensure_area_code_column, ensure_track_areas  # noqa: E402
from app.services.map_hotspots import ensure_map_hotspots  # noqa: E402
from app.services.users import ensure_bootstrap_users  # noqa: E402


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    ensure_area_code_column(engine)
    db = SessionLocal()
    try:
        ensure_bootstrap_users(db)
        ensure_track_areas(db)
        ensure_map_hotspots(db)
    finally:
        db.close()
    Path("tests/uploads").mkdir(parents=True, exist_ok=True)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_client(client):
    login_resp = client.post(
        "/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    assert login_resp.status_code == 303
    return client


def test_login_jimmy_user(client):
    response = client.post(
        "/login",
        data={"username": "Jimmy", "password": "207720"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_login_with_valid_credentials(client):
    response = client.post(
        "/login",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_login_with_invalid_credentials(client):
    response = client.post(
        "/login",
        data={"username": "admin", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert "incorrectos" in response.text


def test_dashboard_requires_login(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_create_and_list_areas(auth_client):
    create_resp = auth_client.post(
        "/api/areas",
        json={
            "name": "Zona de salida",
            "description": "Revisión inicial de pista",
            "expected_upload_interval_minutes": 30,
        },
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["name"] == "Zona de salida"

    list_resp = auth_client.get("/api/areas")
    assert list_resp.status_code == 200
    names = [item["name"] for item in list_resp.json()]
    assert "Zona de salida" in names


def test_upload_photo_for_area(auth_client):
    area = auth_client.post(
        "/api/areas",
        json={
            "name": "Curva norte",
            "description": "Control semanal",
            "expected_upload_interval_minutes": 45,
        },
    ).json()

    upload_resp = auth_client.post(
        f"/api/areas/{area['id']}/photos",
        files={"file": ("foto.jpg", b"fake-image-content", "image/jpeg")},
        data={"notes": "Inspección de mantenimiento"},
    )
    assert upload_resp.status_code == 201
    body = upload_resp.json()
    assert body["area_id"] == area["id"]
    assert "/uploads/" in body["image_url"]

    photos_resp = auth_client.get(f"/api/areas/{area['id']}/photos")
    assert photos_resp.status_code == 200
    assert len(photos_resp.json()) == 1


def test_delete_photo_as_admin(auth_client):
    area = auth_client.post(
        "/api/areas",
        json={"name": "Zona prueba borrado", "expected_upload_interval_minutes": 30},
    ).json()
    photo = auth_client.post(
        f"/api/areas/{area['id']}/photos",
        files={"file": ("foto.jpg", b"fake-image-content", "image/jpeg")},
    ).json()

    delete_resp = auth_client.delete(f"/api/areas/{area['id']}/photos/{photo['id']}")
    assert delete_resp.status_code == 204

    photos_resp = auth_client.get(f"/api/areas/{area['id']}/photos")
    assert photos_resp.status_code == 200
    assert photos_resp.json() == []


def test_delete_photo_as_supervisor(auth_client, client):
    area = auth_client.post(
        "/api/areas",
        json={"name": "Zona supervisor", "expected_upload_interval_minutes": 30},
    ).json()
    photo = auth_client.post(
        f"/api/areas/{area['id']}/photos",
        files={"file": ("foto.jpg", b"otra-foto", "image/jpeg")},
    ).json()

    login_resp = client.post(
        "/login",
        data={"username": "Jimmy", "password": "207720"},
        follow_redirects=False,
    )
    assert login_resp.status_code == 303

    delete_resp = client.delete(f"/api/areas/{area['id']}/photos/{photo['id']}")
    assert delete_resp.status_code == 204


def test_delete_photo_forbidden_for_viewer(auth_client, client):
    db = SessionLocal()
    try:
        from app.models import User
        from app.services.security import hash_password

        viewer = User(
            username="viewer_test",
            password_hash=hash_password("viewer123"),
            role="viewer",
        )
        db.add(viewer)
        db.commit()
    finally:
        db.close()

    area = auth_client.post(
        "/api/areas",
        json={"name": "Zona viewer", "expected_upload_interval_minutes": 30},
    ).json()
    photo = auth_client.post(
        f"/api/areas/{area['id']}/photos",
        files={"file": ("foto.jpg", b"fake-image-content", "image/jpeg")},
    ).json()

    login_resp = client.post(
        "/login",
        data={"username": "viewer_test", "password": "viewer123"},
        follow_redirects=False,
    )
    assert login_resp.status_code == 303

    delete_resp = client.delete(f"/api/areas/{area['id']}/photos/{photo['id']}")
    assert delete_resp.status_code == 403


def test_api_requires_authentication(client):
    response = client.get("/api/areas")
    assert response.status_code == 401


def test_area_detail_page(auth_client):
    response = auth_client.get("/areas/A")
    assert response.status_code == 200
    assert "Área A" in response.text
    assert "Fotos del área A" in response.text


def test_dashboard_shows_track_map(auth_client):
    response = auth_client.get("/")
    assert response.status_code == 200
    assert "Plano de la cancha" in response.text
    assert "Resumen por marcador" in response.text
    assert "A1" in response.text
    assert "B1" in response.text
    assert "L1" in response.text
    assert "Pista de BMX Carlos Ramírez" in response.text
    assert "/static/images/cancha.png" in response.text
    assert "/areas/A" in response.text
    assert "Calibrar posiciones del mapa" in response.text


def test_map_calibration_page(auth_client):
    response = auth_client.get("/admin/mapa-calibracion")
    assert response.status_code == 200
    assert "Calibrar plano de la cancha" in response.text
    assert "A1" in response.text
    assert "L1" in response.text


def test_save_map_calibration(auth_client):
    payload = {
        "hotspots": [
            {
                "label": "A1",
                "area_code": "A",
                "top": 25.0,
                "left": 18.0,
                "width": 2.5,
                "height": 4.9,
                "description": "Test",
                "sort_order": 0,
            }
        ]
    }
    response = auth_client.post("/admin/mapa-calibracion", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["label"] == "A1"


def test_report_page_requires_permission(auth_client, client):
    response = auth_client.get("/reportes")
    assert response.status_code == 200
    assert "Generar reporte PDF" in response.text

    login_resp = client.post(
        "/login",
        data={"username": "Jimmy", "password": "207720"},
        follow_redirects=False,
    )
    assert login_resp.status_code == 303
    jimmy_report = client.get("/reportes")
    assert jimmy_report.status_code == 200


def test_generate_report_pdf(auth_client):
    from io import BytesIO

    from PIL import Image

    image_buffer = BytesIO()
    Image.new("RGB", (40, 30), color="red").save(image_buffer, format="JPEG")
    image_bytes = image_buffer.getvalue()

    area = auth_client.post(
        "/api/areas",
        json={"name": "Zona reporte", "code": "Z", "expected_upload_interval_minutes": 30},
    ).json()
    photo = auth_client.post(
        f"/api/areas/{area['id']}/photos",
        files={"file": ("foto.jpg", image_bytes, "image/jpeg")},
        data={"notes": "Comentario inicial"},
    ).json()

    response = auth_client.post(
        "/reportes/pdf",
        json={
            "title": "Reporte de prueba",
            "photos": [{"photo_id": photo["id"], "notes": "Comentario editado"}],
            "save_notes": True,
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")

    updated = auth_client.get(f"/api/areas/{area['id']}/photos").json()
    assert updated[0]["notes"] == "Comentario editado"
