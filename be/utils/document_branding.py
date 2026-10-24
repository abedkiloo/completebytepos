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


def _store_settings():
    try:
        from settings.models import StoreSettings

        return StoreSettings.load()
    except Exception:
        return None


def resolved_logo_path(*, respect_show_flag: bool = False) -> str | None:
    """Uploaded receipt logo when present, otherwise the packaged brand mark."""
    try:
        store = _store_settings()
        if store is not None:
            if respect_show_flag and not store.receipt_show_logo:
                return None
            if store.receipt_logo:
                path = getattr(store.receipt_logo, 'path', '') or ''
                if path and Path(path).is_file():
                    return path
    except Exception:
        pass
    if respect_show_flag:
        store = _store_settings()
        if store is not None and not store.receipt_show_logo:
            return None
    fallback = default_brand_logo_path()
    return str(fallback) if fallback.is_file() else None


def brand_name_line() -> str:
    return resolved_store_name() or DEFAULT_STORE_NAME


def brand_header_text() -> str:
    """Optional store letterhead / receipt header from System Settings."""
    store = _store_settings()
    if store is None:
        return ''
    return (getattr(store, 'receipt_header_text', None) or '').strip()


def _default_tenant():
    try:
        from settings.models import Tenant

        return Tenant.get_default_tenant()
    except Exception:
        return None


def brand_address_line() -> str:
    tenant = _default_tenant()
    if tenant is None:
        return ''
    parts = [
        (tenant.address or '').strip(),
        (tenant.city or '').strip(),
        (tenant.country or '').strip(),
    ]
    return ', '.join(p for p in parts if p)


def brand_phone() -> str:
    tenant = _default_tenant()
    phone = (getattr(tenant, 'phone', None) or '').strip() if tenant else ''
    return phone or DEFAULT_CONTACT_PHONE


def brand_contact_line() -> str:
    phone = brand_phone()
    return f'{DEFAULT_TAGLINE} · Tel: {phone}'


def branded_document_title(document_title: str) -> str:
    name = brand_name_line()
    title = str(document_title or '').strip()
    if not title:
        return name
    if title.lower().startswith(name.lower()):
        return title
    return f'{name} — {title}'


def brand_header_elements(
    document_title: str = '',
    *,
    logo_size=1.15 * inch,
    extra_letterhead: str = '',
    respect_logo_flag: bool = False,
):
    """Logo, store name, tagline, contact, then the document title — used on every PDF.

    Uses System Settings store name / logo / phone / address / receipt header when set.
    ``extra_letterhead`` is for document-specific lines (e.g. Payroll letterhead).
    """
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
        spaceAfter=4,
    )
    letter_style = ParagraphStyle(
        'BrandLetterhead',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#555555'),
        spaceAfter=4,
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
    logo = resolved_logo_path(respect_show_flag=respect_logo_flag)
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
    elements.append(Paragraph(f'Tel: {brand_phone()}', contact_style))
    address = brand_address_line()
    if address:
        elements.append(Paragraph(address.replace('\n', '<br/>'), letter_style))
    header_text = brand_header_text()
    if header_text:
        elements.append(Paragraph(header_text.replace('\n', '<br/>'), letter_style))
    extra = (extra_letterhead or '').strip()
    if extra:
        elements.append(Paragraph(extra.replace('\n', '<br/>'), letter_style))
    elements.append(Spacer(1, 4))
    title = str(document_title or '').strip()
    if title:
        elements.append(Paragraph(title, title_style))
    return elements
