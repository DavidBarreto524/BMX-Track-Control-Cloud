from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse

import httpx
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, PageBreak

from app.config import settings
from app.services.timezone import format_datetime, format_now_colombia


@dataclass
class ReportPhotoEntry:
    area_label: str
    uploaded_at: datetime
    notes: str | None
    image_path: Path


def _resolve_local_image_path(image_url: str) -> Path | None:
    if not image_url.startswith("/uploads/"):
        return None
    filename = image_url.removeprefix("/uploads/").lstrip("/")
    path = Path(settings.local_upload_dir) / filename
    return path if path.is_file() else None


def _download_remote_image(image_url: str) -> Path:
    suffix = Path(urlparse(image_url).path).suffix or ".jpg"
    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.get(image_url)
        response.raise_for_status()
        with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(response.content)
            return Path(tmp.name)


def resolve_photo_image_path(image_url: str) -> Path:
    local_path = _resolve_local_image_path(image_url)
    if local_path:
        return local_path
    if image_url.startswith("http://") or image_url.startswith("https://"):
        return _download_remote_image(image_url)
    raise ValueError(f"No se pudo cargar la imagen: {image_url}")


def _scaled_image_flowable(image_path: Path, max_width: float, max_height: float) -> RLImage:
    with PILImage.open(image_path) as img:
        width_px, height_px = img.size
    width_pt = max_width
    height_pt = width_pt * height_px / width_px
    if height_pt > max_height:
        height_pt = max_height
        width_pt = height_pt * width_px / height_px
    return RLImage(str(image_path), width=width_pt, height=height_pt)


def build_photos_pdf(
    title: str,
    entries: list[ReportPhotoEntry],
    generated_by: str | None = None,
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title=title,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=18,
        spaceAfter=8,
        textColor=colors.HexColor("#1a1a1a"),
    )
    meta_style = ParagraphStyle(
        "ReportMeta",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#555555"),
        spaceAfter=6,
    )
    heading_style = ParagraphStyle(
        "PhotoHeading",
        parent=styles["Heading2"],
        fontSize=13,
        spaceBefore=6,
        spaceAfter=4,
        textColor=colors.HexColor("#212529"),
    )
    notes_style = ParagraphStyle(
        "PhotoNotes",
        parent=styles["Normal"],
        fontSize=11,
        leading=14,
        spaceAfter=8,
        textColor=colors.HexColor("#333333"),
    )

    story: list = []
    story.append(Paragraph(title, title_style))
    story.append(
        Paragraph(
            f"Generado: {format_now_colombia()} (hora Colombia)",
            meta_style,
        )
    )
    if generated_by:
        story.append(Paragraph(f"Usuario: {generated_by}", meta_style))
    story.append(Paragraph(f"Total de fotos: {len(entries)}", meta_style))
    story.append(Spacer(1, 0.4 * cm))

    max_width = doc.width
    max_height = 11 * cm

    for index, entry in enumerate(entries):
        if index > 0:
            story.append(PageBreak())
        area_text = entry.area_label.replace("&", "&amp;")
        date_text = format_datetime(entry.uploaded_at)
        story.append(Paragraph(f"{area_text} — {date_text}", heading_style))
        notes = (entry.notes or "").strip()
        if notes:
            safe_notes = notes.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            safe_notes = safe_notes.replace("\n", "<br/>")
            story.append(Paragraph(f"<b>Comentario:</b> {safe_notes}", notes_style))
        else:
            story.append(Paragraph("<i>Sin comentario</i>", notes_style))
        story.append(_scaled_image_flowable(entry.image_path, max_width, max_height))

    doc.build(story)
    return buffer.getvalue()
