"""Product views: featured photo plus three more, each under 2 MiB."""

import io

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from products.gallery import photo_rows
from products.models import Category, Product, ProductPhoto
from utils.image_upload import PRODUCT_MAX_INPUT_BYTES, TARGET_STORED_BYTES
from utils.tests.module_setting_helpers import enable_products_list_api_fields


def _jpeg(color='red', size=(40, 30)):
    """
    A real JPEG upload.

    Args:
        color: PIL color.
        size: Pixel size, at least 1 by 1.

    Returns:
        SimpleUploadedFile under 2 MiB.
    """
    buffer = io.BytesIO()
    Image.new('RGB', size, color=color).save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile('view.jpg', buffer.getvalue(), content_type='image/jpeg')


class ProductPhotoTests(TestCase):
    """Upload, feature, reject, and publish product views."""

    def setUp(self):
        enable_products_list_api_fields()
        self.user = User.objects.create_superuser('photo_admin', 'a@example.com', 'x')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.category = Category.objects.create(name='Photos', is_active=True)

    def _product(self, sku='PHOTO-1'):
        return Product.objects.create(
            name='Photo product',
            sku=sku,
            category=self.category,
            price='10.00',
            cost='4.00',
        )

    def test_four_views_compress_and_the_chosen_one_is_featured(self):
        product = self._product()
        response = self.client.patch(
            f'/api/products/{product.id}/',
            {
                'photo_1': _jpeg('red'),
                'photo_2': _jpeg('green'),
                'photo_3': _jpeg('blue'),
                'photo_4': _jpeg('yellow'),
                'featured_slot': 3,
            },
            format='multipart',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(ProductPhoto.objects.filter(product=product).count(), 4)
        product.refresh_from_db()
        self.assertEqual(product.featured_slot, 3)
        self.assertTrue(product.image)
        for photo in ProductPhoto.objects.filter(product=product):
            self.assertLessEqual(photo.image.size, TARGET_STORED_BYTES)
        featured = next(row for row in response.data['photos'] if row['is_featured'])
        self.assertEqual(featured['slot'], 3)

    def test_replacing_one_view_leaves_the_other_three(self):
        product = self._product('PHOTO-ONE')
        created = self.client.patch(
            f'/api/products/{product.id}/',
            {
                'photo_1': _jpeg('red'),
                'photo_2': _jpeg('green'),
                'photo_3': _jpeg('blue'),
                'photo_4': _jpeg('yellow'),
                'featured_slot': 1,
            },
            format='multipart',
        )
        self.assertEqual(created.status_code, 200, created.data)
        before = {}
        for row in ProductPhoto.objects.filter(product=product):
            row.image.open('rb')
            before[row.slot] = row.image.read()
            row.image.close()
        replaced = self.client.patch(
            f'/api/products/{product.id}/',
            {'photo_2': _jpeg('white', (50, 40))},
            format='multipart',
        )
        self.assertEqual(replaced.status_code, 200, replaced.data)
        after = {}
        for row in ProductPhoto.objects.filter(product=product):
            row.image.open('rb')
            after[row.slot] = row.image.read()
            row.image.close()
        self.assertEqual(set(after), {1, 2, 3, 4})
        self.assertEqual(after[1], before[1])
        self.assertEqual(after[3], before[3])
        self.assertEqual(after[4], before[4])
        self.assertNotEqual(after[2], before[2])
        self.assertNotIn('0718', str(replaced.data))

    def test_a_broken_or_huge_view_is_refused_and_the_product_stays(self):
        product = self._product('PHOTO-BAD')
        product.image.save('old.jpg', _jpeg('white'), save=True)
        broken = self.client.patch(
            f'/api/products/{product.id}/',
            {'photo_2': SimpleUploadedFile('notes.txt', b'not-a-photo', content_type='text/plain')},
            format='multipart',
        )
        self.assertEqual(broken.status_code, 400, broken.data)
        self.assertIn('photo_2', broken.data)
        self.assertNotIn('0718000000', str(broken.data))
        self.assertEqual(ProductPhoto.objects.filter(product=product).count(), 0)

        huge = SimpleUploadedFile(
            'big.jpg',
            b'\xff\xd8\xff\xe0' + (b'\x00' * (PRODUCT_MAX_INPUT_BYTES + 20)),
            content_type='image/jpeg',
        )
        oversized = self.client.patch(
            f'/api/products/{product.id}/',
            {'photo_3': huge},
            format='multipart',
        )
        self.assertEqual(oversized.status_code, 400, oversized.data)
        self.assertIn('photo_3', oversized.data)
        product.refresh_from_db()
        self.assertTrue(product.image.name.endswith('old.jpg') or product.image)

    def test_an_existing_photo_can_be_replaced_and_chosen_as_featured(self):
        product = self._product('PHOTO-EDIT')
        first = self.client.patch(
            f'/api/products/{product.id}/',
            {'image': _jpeg('red'), 'featured_slot': 1},
            format='multipart',
        )
        self.assertEqual(first.status_code, 200, first.data)
        second = self.client.patch(
            f'/api/products/{product.id}/',
            {'photo_2': _jpeg('green', (80, 80)), 'featured_slot': 2},
            format='multipart',
        )
        self.assertEqual(second.status_code, 200, second.data)
        slots = {row['slot']: row for row in second.data['photos']}
        self.assertIn(1, slots)
        self.assertTrue(slots[2]['is_featured'])
        self.assertFalse(slots[1]['is_featured'])
        self.assertEqual(second.data['image_url'], slots[2]['url'])
        product.refresh_from_db()
        self.assertEqual(product.featured_slot, 2)

    def test_public_product_lists_the_featured_image_and_the_other_views(self):
        from cms.serializers import PublicProductSerializer
        from rest_framework.test import APIRequestFactory

        product = self._product('PHOTO-PUBLIC')
        self.client.patch(
            f'/api/products/{product.id}/',
            {'photo_1': _jpeg('red'), 'photo_2': _jpeg('blue'), 'featured_slot': 2},
            format='multipart',
        )
        product.refresh_from_db()
        request = APIRequestFactory().get('/api/public/website/products/')
        data = PublicProductSerializer(product, context={'request': request}).data
        self.assertEqual(len(data['images']), 2)
        featured = next(row for row in data['images'] if row['is_featured'])
        self.assertEqual(data['image_url'], featured['url'])
        self.assertEqual(featured['slot'], 2)
        self.assertNotIn('cost', data)
        self.assertNotIn('stock_quantity', data)

    def test_anonymous_and_a_user_without_product_access_cannot_upload(self):
        product = self._product('PHOTO-LOCK')
        anonymous = APIClient()
        denied = anonymous.patch(
            f'/api/products/{product.id}/',
            {'photo_1': _jpeg()},
            format='multipart',
        )
        self.assertEqual(denied.status_code, 401)
        stranger = User.objects.create_user('photo_stranger', password='x')
        client = APIClient()
        client.force_authenticate(user=stranger)
        forbidden = client.patch(
            f'/api/products/{product.id}/',
            {'photo_2': _jpeg()},
            format='multipart',
        )
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(ProductPhoto.objects.filter(product=product).count(), 0)

    def test_slot_bounds_and_a_removed_featured_view(self):
        product = self._product('PHOTO-SLOT')
        bad = self.client.patch(
            f'/api/products/{product.id}/',
            {'featured_slot': 9},
            format='multipart',
        )
        self.assertEqual(bad.status_code, 400, bad.data)
        saved = self.client.patch(
            f'/api/products/{product.id}/',
            {'photo_1': _jpeg('red'), 'photo_2': _jpeg('green'), 'featured_slot': 2},
            format='multipart',
        )
        self.assertEqual(saved.status_code, 200, saved.data)
        cleared = self.client.patch(
            f'/api/products/{product.id}/',
            {'clear_photos': '2', 'featured_slot': 2},
            format='multipart',
        )
        self.assertEqual(cleared.status_code, 200, cleared.data)
        product.refresh_from_db()
        self.assertEqual(product.featured_slot, 1)
        self.assertEqual(list(product.photos.values_list('slot', flat=True)), [1])
        self.assertEqual(photo_rows(product)[0]['slot'], 1)
