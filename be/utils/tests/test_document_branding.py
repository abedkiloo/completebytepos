"""Document brand mark, name, and contact on generated files."""

from django.test import SimpleTestCase
from unittest.mock import MagicMock, patch

from utils.document_branding import (
    DEFAULT_CONTACT_PHONE,
    DEFAULT_TAGLINE,
    brand_contact_line,
    brand_header_elements,
    brand_name_line,
    branded_document_title,
    default_brand_logo_path,
    resolved_logo_path,
)


class DocumentBrandingTests(SimpleTestCase):
    def test_packaged_logo_exists(self):
        self.assertTrue(default_brand_logo_path().is_file())
        self.assertTrue(resolved_logo_path())

    def test_brand_lines(self):
        self.assertEqual(brand_name_line(), 'Omuwenga Suppliers')
        self.assertIn(DEFAULT_TAGLINE, brand_contact_line())
        self.assertIn(DEFAULT_CONTACT_PHONE, brand_contact_line())

    def test_branded_document_title(self):
        self.assertEqual(branded_document_title(''), 'Omuwenga Suppliers')
        self.assertEqual(
            branded_document_title('Sales Report'),
            'Omuwenga Suppliers — Sales Report',
        )
        self.assertEqual(
            branded_document_title('Omuwenga Suppliers invoice'),
            'Omuwenga Suppliers invoice',
        )

    def test_header_includes_logo_name_tagline_contact_and_title(self):
        elements = brand_header_elements('Sales Report')
        self.assertGreaterEqual(len(elements), 4)
        texts = [getattr(el, 'text', '') for el in elements]
        self.assertTrue(any('Omuwenga Suppliers' in text for text in texts))
        self.assertTrue(any(DEFAULT_TAGLINE in text for text in texts))
        self.assertTrue(any(DEFAULT_CONTACT_PHONE in text for text in texts))
        self.assertTrue(any('Sales Report' in text for text in texts))

    def test_header_omits_blank_title(self):
        elements = brand_header_elements('   ')
        texts = [getattr(el, 'text', '') or '' for el in elements]
        self.assertTrue(any('Omuwenga Suppliers' in text for text in texts))
        self.assertFalse(any(text.strip() == 'Sales Report' for text in texts))

    def test_uploaded_logo_preferred_when_file_exists(self):
        logo = default_brand_logo_path()
        store = MagicMock()
        store.receipt_logo = MagicMock(path=str(logo))
        with patch('settings.models.StoreSettings.load', return_value=store):
            self.assertEqual(resolved_logo_path(), str(logo))

    def test_missing_upload_falls_back_to_packaged_logo(self):
        store = MagicMock()
        store.receipt_logo = MagicMock(path='/not/a/real/logo.png')
        with patch('settings.models.StoreSettings.load', return_value=store):
            self.assertEqual(resolved_logo_path(), str(default_brand_logo_path()))

    def test_settings_error_falls_back_to_packaged_logo(self):
        with patch('settings.models.StoreSettings.load', side_effect=RuntimeError('no db')):
            self.assertEqual(resolved_logo_path(), str(default_brand_logo_path()))

    def test_header_survives_logo_draw_failure(self):
        with patch('utils.document_branding.Image', side_effect=OSError('bad image')):
            elements = brand_header_elements('Invoice')
        texts = [getattr(el, 'text', '') for el in elements]
        self.assertTrue(any('Omuwenga Suppliers' in text for text in texts))
        self.assertTrue(any('Invoice' in text for text in texts))

    def test_empty_upload_uses_packaged_logo(self):
        store = MagicMock()
        store.receipt_logo = None
        with patch('settings.models.StoreSettings.load', return_value=store):
            self.assertEqual(resolved_logo_path(), str(default_brand_logo_path()))

    def test_missing_packaged_file_returns_none(self):
        from pathlib import Path

        with patch(
            'utils.document_branding.default_brand_logo_path',
            return_value=Path('/definitely-missing-omuwenga.jpg'),
        ), patch('settings.models.StoreSettings.load', side_effect=RuntimeError('no db')):
            self.assertIsNone(resolved_logo_path())

    def test_header_without_logo_file_still_has_name(self):
        with patch('utils.document_branding.resolved_logo_path', return_value=None):
            elements = brand_header_elements('Quote')
        texts = [getattr(el, 'text', '') for el in elements]
        self.assertTrue(any('Omuwenga Suppliers' in text for text in texts))
        self.assertTrue(any('Quote' in text for text in texts))
