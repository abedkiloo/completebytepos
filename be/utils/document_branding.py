"""Shared store brand mark, name, and contact for generated documents."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, Spacer

from settings.store_settings_helpers import DEFAULT_STORE_NAME, resolved_store_name

DEFAULT_TAGLINE = 'Think Furniture, Think Omuwenga'
DEFAULT_CONTACT_PHONE = '0718515142'
DEFAULT_BRAND_LOGO = Path(__file__).resolve().parent / 'branding' / 'omuwenga_logo.jpg'


def default_brand_logo_path() -> Path:
    return DEFAULT_BRAND_LOGO


def resolved_logo_path() -> str | None:
    """Uploaded receipt logo when present, otherwise the packaged brand mark."""
    try:
        from settings.models import StoreSettings

        store = StoreSettings.load()
        if store.receipt_logo:
            path = getattr(store.receipt_logo, 'path', '') or ''
            if path and Path(path).is_file():
                return path
    except Exception:
        pass
    fallback = default_brand_logo_path()
    return str(fallback) if fallback.is_file() else None


def brand_name_line() -> str:
    return resolved_store_name() or DEFAULT_STORE_NAME


def brand_contact_line() -> str:
    return f'{DEFAULT_TAGLINE} · Tel: {DEFAULT_CONTACT_PHONE}'


def branded_document_title(document_title: str) -> str:
    name = brand_name_line()
    title = str(document_title or '').strip()
    if not title:
        return name
    if title.lower().startswith(name.lower()):
        return title
    return f'{name} — {title}'


def brand_header_elements(document_title: str = '', *, logo_size=1.15 * inch):
    """Logo, store name, tagline, contact, then the document title — used on every PDF."""
    styles = getSampleStyleSheet()
    name_style = ParagraphStyle(
        'BrandName',
        parent=styles['Heading1'],
        fontSize=14,
        leading=18,
        alignment=TA_CENTER,
        spaceAfter=2,
        textColor=colors.HexColor('#1a4d7a'),
    )
    tag_style = ParagraphStyle(
        'BrandTagline',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#5B2C8A'),
        spaceAfter=2,
    )
    contact_style = ParagraphStyle(
        'BrandContact',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#333333'),
        spaceAfter=8,
    )
    title_style = ParagraphStyle(
        'BrandDocTitle',
        parent=styles['Heading2'],
        fontSize=12,
        leading=15,
        alignment=TA_CENTER,
        spaceAfter=10,
        textColor=colors.HexColor('#1a1a1a'),
    )
    elements = []
    logo = resolved_logo_path()
    if logo:
        try:
            image = Image(logo, width=logo_size, height=logo_size)
            image.hAlign = 'CENTER'
            elements.append(image)
            elements.append(Spacer(1, 6))
        except Exception:
            pass
    elements.append(Paragraph(brand_name_line(), name_style))
    elements.append(Paragraph(DEFAULT_TAGLINE, tag_style))
    elements.append(Paragraph(f'Tel: {DEFAULT_CONTACT_PHONE}', contact_style))
    title = str(document_title or '').strip()
    if title:
        elements.append(Paragraph(title, title_style))
    return elements
