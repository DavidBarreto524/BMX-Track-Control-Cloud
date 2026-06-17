from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AreaCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    code: str | None = Field(default=None, min_length=1, max_length=10)
    description: str | None = None
    expected_upload_interval_minutes: int | None = Field(default=None, ge=5, le=1440)


class AreaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str | None = None
    name: str
    description: str | None
    expected_upload_interval_minutes: int
    created_at: datetime
    last_uploaded_at: datetime | None = None
    upload_status: str = "Sin fotos"


class PhotoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    area_id: int
    image_url: str
    notes: str | None
    uploaded_at: datetime


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    area_id: int
    message: str
    created_at: datetime
    resolved: bool


class MapHotspotItem(BaseModel):
    label: str = Field(min_length=1, max_length=10)
    area_code: str = Field(min_length=1, max_length=10)
    top: float = Field(ge=0, le=100)
    left: float = Field(ge=0, le=100)
    width: float = Field(default=2.5, ge=0.5, le=20)
    height: float = Field(default=4.9, ge=0.5, le=20)
    description: str | None = None
    sort_order: int = 0


class MapHotspotSave(BaseModel):
    hotspots: list[MapHotspotItem]


class ReportPhotoItem(BaseModel):
    photo_id: int = Field(ge=1)
    notes: str | None = None


class ReportGenerateRequest(BaseModel):
    title: str = Field(default="Reporte de fotos BMX", min_length=1, max_length=200)
    photos: list[ReportPhotoItem] = Field(min_length=1)
    save_notes: bool = False


class PhotoNotesUpdate(BaseModel):
    notes: str | None = None

