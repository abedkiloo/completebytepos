"""Tests for the lightweight barcode shim package."""

from io import BytesIO
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from barcode import Code128, EAN13, EAN8, ImageWriter

class ImageWriterTests(SimpleTestCase):
    def test_write_produces_png_bytes(self):
        writer = ImageWriter()
        buffer = BytesIO()
        writer.write(buffer)
        self.assertTrue(buffer.getvalue().startswith(b'\x89PNG'))


class BarcodeCodeTests(SimpleTestCase):
    def test_code128_writes_value_to_buffer(self):
        code = Code128('ABC123', writer=ImageWriter())
        buffer = BytesIO()
        code.write(buffer)
        self.assertGreater(len(buffer.getvalue()), 0)

    def test_ean_variants_write(self):
        for cls, value in ((EAN13, '123456789012'), (EAN8, '1234567')):
            code = cls(value, writer=ImageWriter())
            buffer = BytesIO()
            code.write(buffer)
            self.assertGreater(len(buffer.getvalue()), 0)

    def test_write_without_capable_writer_raises(self):
        code = Code128('X', writer=MagicMock(spec=[]))
        with self.assertRaises(RuntimeError):
            code.write(BytesIO())
