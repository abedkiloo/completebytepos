from django.test import SimpleTestCase, override_settings

from config.media_urls import absolute_media_url


class AbsoluteMediaUrlTests(SimpleTestCase):
    @override_settings(
        MEDIA_PUBLIC_BASE_URL='http://shop.example:3000',
        PUBLIC_HOST='',
    )
    def test_uses_media_public_base_url(self):
        url = absolute_media_url(None, '/media/products/a.jpg')
        self.assertEqual(url, 'http://shop.example:3000/media/products/a.jpg')

    @override_settings(
        MEDIA_PUBLIC_BASE_URL='',
        PUBLIC_HOST='193.37.213.177',
        MEDIA_PUBLIC_PORT=3000,
    )
    def test_falls_back_to_public_host(self):
        url = absolute_media_url(None, 'media/products/b.jpg')
        self.assertEqual(url, 'http://193.37.213.177:3000/media/products/b.jpg')
