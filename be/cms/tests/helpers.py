from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image


def png_upload(name='cover.png'):
    buf = BytesIO()
    Image.new('RGB', (4, 4), (200, 120, 40)).save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')
