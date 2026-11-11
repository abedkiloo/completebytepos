"""Shared image compress / size-cap helpers."""

from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from utils.image_upload import (
    GENERAL_MAX_INPUT_BYTES,
    PRODUCT_MAX_INPUT_BYTES,
    TARGET_STORED_BYTES,
    compress_image_bytes,
    prepare_uploaded_image,
)


def _png_bytes(width=800, height=600, color=(20, 120, 200)) -> bytes:
    buf = BytesIO()
    Image.new('RGB', (width, height), color=color).save(buf, format='PNG')
    return buf.getvalue()


def _large_png_over(limit: int) -> bytes:
    """Build an image larger than ``limit`` bytes."""
    # Random-ish noise compresses poorly → large file quickly.
    import os

    size = 2200
    img = Image.frombytes(
        'RGB',
        (size, size),
        os.urandom(size * size * 3),
    )
    buf = BytesIO()
    img.save(buf, format='JPEG', quality=95)
    data = buf.getvalue()
    if len(data) <= limit:
        img = Image.new('RGB', (5000, 5000), color=(90, 40, 10))
        buf = BytesIO()
        img.save(buf, format='JPEG', quality=100)
        data = buf.getvalue()
    assert len(data) > limit, len(data)
    return data


class ImageUploadHelperTests(SimpleTestCase):
    def test_compress_brings_large_image_under_target(self):
        raw = _large_png_over(TARGET_STORED_BYTES)
        out = compress_image_bytes(raw, target_bytes=TARGET_STORED_BYTES)
        self.assertLessEqual(len(out), TARGET_STORED_BYTES)
        self.assertGreater(len(out), 100)
        # Output must open as JPEG.
        img = Image.open(BytesIO(out))
        self.assertEqual((img.format or '').upper(), 'JPEG')

    def test_prepare_rejects_product_over_2mb(self):
        raw = b'\xff\xd8\xff' + (b'\x00' * (PRODUCT_MAX_INPUT_BYTES + 50))
        upload = SimpleUploadedFile('big.jpg', raw, content_type='image/jpeg')
        with self.assertRaises(ValidationError) as ctx:
            prepare_uploaded_image(
                upload,
                field_name='image',
                max_input_bytes=PRODUCT_MAX_INPUT_BYTES,
                label='Product photo',
            )
        self.assertIn('image', ctx.exception.message_dict)
        self.assertIn('2 MB', str(ctx.exception.message_dict['image']))

    def test_prepare_general_accepts_under_5mb_and_compresses(self):
        raw = _png_bytes(1200, 900)
        upload = SimpleUploadedFile('note.png', raw, content_type='image/png')
        prepared = prepare_uploaded_image(
            upload,
            field_name='image',
            max_input_bytes=GENERAL_MAX_INPUT_BYTES,
            target_bytes=TARGET_STORED_BYTES,
            label='Note photo',
            preferred_name='note.png',
        )
        self.assertIsNotNone(prepared)
        self.assertTrue(prepared.name.endswith('.jpg'))
        self.assertLessEqual(prepared.size, TARGET_STORED_BYTES)

    def test_prepare_none_passthrough(self):
        self.assertIsNone(prepare_uploaded_image(None))

    def test_rejects_non_image(self):
        upload = SimpleUploadedFile('x.txt', b'not-an-image', content_type='text/plain')
        with self.assertRaises(ValidationError):
            prepare_uploaded_image(upload, field_name='image', label='Photo')
