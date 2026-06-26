from app.services.pdf_report import report_pdf_content_disposition, report_pdf_filename


def test_report_pdf_filename_uses_title():
    assert report_pdf_filename("Reporte de prueba") == "Reporte de prueba.pdf"


def test_report_pdf_filename_strips_invalid_characters():
    assert report_pdf_filename('Inspección: zona "A"') == "Inspección zona A.pdf"


def test_report_pdf_filename_avoids_duplicate_pdf_extension():
    assert report_pdf_filename("Mi reporte.PDF") == "Mi reporte.PDF"


def test_report_pdf_content_disposition_supports_unicode_title():
    header = report_pdf_content_disposition("Reporte — Pista BMX")
    assert "filename*=" in header
    assert header.endswith(".pdf'") or ".pdf" in header
