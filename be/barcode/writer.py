from io import BytesIO
from PIL import Image, ImageDraw


class ImageWriter:
    def __init__(self):
        pass

    def write(self, buffer, options=None):
        img = Image.new('RGB', (200, 80), color='white')
        d = ImageDraw.Draw(img)
        d.text((10, 30), 'BARCODE', fill='black')
        img.save(buffer, format='PNG')
        buffer.seek(0)
