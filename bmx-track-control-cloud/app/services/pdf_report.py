from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse

import httpx
from PIL import Image as PILImage
from PIL import ImageOps
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image as RLImage, PageBreak, Paragraph, SimpleDocTemplate, Spacer

from app.config import settings
from app.services.timezone import format_datetime, format_now_colombia

PHOTOS_PER_PAGE = 2
HEADER_FIRST_PAGE_HEIGHT = 3.2 * cm
CAPTION_BLOCK_HEIGHT = 2.0 * cm
PHOTO_ROW_GAP = 0.35 * cm


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


def _prepare_image_for_pdf(image_path: Path, temp_files: list[Path]) -> tuple[Path, int, int]:
    with PILImage.open(image_path) as img:
        corrected = ImageOps.exif_transpose(img)
        if corrected.mode in ("RGBA", "P", "LA"):
            corrected = corrected.convert("RGB")
        width_px, height_px = corrected.size
        with NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            corrected.save(tmp.name, format="JPEG", quality=92)
            prepared_path = Path(tmp.name)
    temp_files.append(prepared_path)
    return prepared_path, width_px, height_px


def _scaled_image_flowable(
    image_path: Path,
    width_px: int,
    height_px: int,
    max_width: float,
    max_height: float,
) -> RLImage:
    width_pt = max_width
    height_pt = width_pt * height_px / width_px
    if height_pt > max_height:
        height_pt = max_height
        width_pt = height_pt * width_px / height_px
    return RLImage(str(image_path), width=width_pt, height=height_pt)


def _chunk_entries(entries: list[ReportPhotoEntry]) -> list[list[ReportPhotoEntry]]:
    return [
        entries[index : index + PHOTOS_PER_PAGE]
        for index in range(0, len(entries), PHOTOS_PER_PAGE)
    ]


def _image_max_height(doc: SimpleDocTemplate, photos_on_page: int, is_first_page: bool) -> float:
    available = doc.height
    if is_first_page:
        available -= HEADER_FIRST_PAGE_HEIGHT
    available -= PHOTO_ROW_GAP * max(photos_on_page - 1, 0)
    available -= CAPTION_BLOCK_HEIGHT * photos_on_page
    return max(available / photos_on_page, 4 * cm)


def build_photos_pdf(
    title: str,
    entries: list[ReportPhotoEntry],
    generated_by: str | None = None,
) -> tuple[bytes, list[Path]]:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.6 * cm,
        leftMargin=1.6 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
        title=title,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=17,
        spaceAfter=6,
        textColor=colors.HexColor("#1a1a1a"),
    )
    meta_style = ParagraphStyle(
        "ReportMeta",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#555555"),
        spaceAfter=4,
    )
    heading_style = ParagraphStyle(
        "PhotoHeading",
        parent=styles["Heading2"],
        fontSize=11,
        spaceBefore=2,
        spaceAfter=2,
        textColor=colors.HexColor("#212529"),
    )
    notes_style = ParagraphStyle(
        "PhotoNotes",
        parent=styles["Normal"],
        fontSize=9,
        leading=11,
        spaceAfter=4,
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
    story.append(Spacer(1, 0.25 * cm))

    temp_files: list[Path] = []
    max_width = doc.width
    page_chunks = _chunk_entries(entries)

    for page_index, chunk in enumerate(page_chunks):
        if page_index > 0:
            story.append(PageBreak())

        image_max_height = _image_max_height(
            doc,
            photos_on_page=len(chunk),
            is_first_page=page_index == 0,
        )

        for photo_index, entry in enumerate(chunk):
            if photo_index > 0:
                story.append(Spacer(1, PHOTO_ROW_GAP))

            prepared_path, width_px, height_px = _prepare_image_for_pdf(entry.image_path, temp_files)

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

            story.append(
                _scaled_image_flowable(
                    prepared_path,
                    width_px,
                    height_px,
                    max_width,
                    image_max_height,
                )
            )

    doc.build(story)
    return buffer.getvalue(), temp_files
