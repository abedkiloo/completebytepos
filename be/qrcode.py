from PIL import Image, ImageDraw


class _Constants:
    ERROR_CORRECT_L = 1


constants = _Constants()


class QRCode:
    def __init__(self, version=1, error_correction=None, box_size=10, border=2):
        self.version = version
        self.error_correction = error_correction
        self.box_size = box_size
        self.border = border
        self._data = []

    def add_data(self, data):
        self._data.append(str(data))

    def make(self, fit=True):
        return True

    def make_image(self, fill_color="black", back_color="white"):
        # Simple placeholder image containing the data text
        img = Image.new('RGB', (max(100, self.box_size * 10), max(100, self.box_size * 10)), color=back_color)
        d = ImageDraw.Draw(img)
        text = ' '.join(self._data)[:200]
        d.text((10, 10), text, fill=fill_color)
        return img


def make(data=None, **kwargs):
    qr = QRCode(**kwargs)
    if data is not None:
        qr.add_data(data)
    qr.make(fit=True)
    return qr
