from io import BytesIO
from PIL import Image, ImageDraw
from .writer import ImageWriter


class _BaseCode:
    def __init__(self, value, writer=None):
        self.value = value
        self.writer = writer or ImageWriter()

    def write(self, buffer, options=None):
        if hasattr(self.writer, 'write'):
            img = Image.new('RGB', (200, 80), color='white')
            d = ImageDraw.Draw(img)
            d.text((10, 30), str(self.value), fill='black')
            img.save(buffer, format='PNG')
            buffer.seek(0)
        else:
            raise RuntimeError('No writer available to render barcode')


class Code128(_BaseCode):
    pass


class EAN13(_BaseCode):
    pass


class EAN8(_BaseCode):
    pass

__all__ = ['Code128', 'EAN13', 'EAN8', 'ImageWriter']
