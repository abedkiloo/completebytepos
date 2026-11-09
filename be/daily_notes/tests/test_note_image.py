"""Optional daily note image upload."""

from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework import status

from daily_notes.models import DailyNote
from utils.tests.api_test_base import ManagerAPITestCase


def _jpeg_bytes(name='note.jpg'):
    buf = BytesIO()
    Image.new('RGB', (32, 32), color=(40, 120, 200)).save(buf, format='JPEG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/jpeg')


class DailyNoteImageUploadTests(ManagerAPITestCase):
    def test_create_without_image(self):
        res = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': '2026-11-09',
                'content': 'Handover without photo',
                'priority': 'medium',
            },
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        note = DailyNote.objects.get(pk=res.data['id'])
        self.assertFalse(bool(note.image))
        self.assertIsNone(res.data.get('image_url'))

    def test_create_with_optional_image(self):
        res = self.client.post(
            '/api/daily-notes/notes/',
            {
                'note_date': '2026-11-09',
                'content': 'Damaged stock with photo',
                'priority': 'high',
                'image': _jpeg_bytes(),
            },
            format='multipart',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        note = DailyNote.objects.get(pk=res.data['id'])
        self.assertTrue(bool(note.image))
        self.assertTrue(res.data.get('image_url'))

    def test_list_includes_image_url(self):
        note = DailyNote.objects.create(
            note_date='2026-11-09',
            content='Listed with image',
            author=self.manager_user,
        )
        note.image.save('list.jpg', _jpeg_bytes('list.jpg'), save=True)
        res = self.client.get('/api/daily-notes/notes/', {'note_date': '2026-11-09'})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        rows = res.data.get('results', res.data)
        match = next(r for r in rows if r['id'] == note.id)
        self.assertTrue(match.get('image_url'))
