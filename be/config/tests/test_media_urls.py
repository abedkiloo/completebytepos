from django.test import SimpleTestCase, override_settings

from config.media_urls import absolute_media_url


class MediaUrlsTests(SimpleTestCase):
    @override_settings(MEDIA_PUBLIC_BASE_URL='http://shop:3000')
    def test_public_base(self):
        url = absolute_media_url(None, '/media/products/x.jpg')
        self.assertEqual(url, 'http://shop:3000/media/products/x.jpg')

    @override_settings(
        MEDIA_PUBLIC_BASE_URL='',
        PUBLIC_HOST='10.0.0.1',
        MEDIA_PUBLIC_PORT=3000,
    )
    def test_public_host_fallback(self):
        url = absolute_media_url(None, 'media/x.jpg')
        self.assertEqual(url, 'http://10.0.0.1:3000/media/x.jpg')

    @override_settings(MEDIA_PUBLIC_BASE_URL='', PUBLIC_HOST='')
    def test_internal_hostname_returns_relative_path(self):
        from django.test import RequestFactory

        request = RequestFactory().get(
            '/api/products/',
            HTTP_HOST='backend:8000',
        )
        url = absolute_media_url(request, '/media/products/x.jpg')
        self.assertEqual(url, '/media/products/x.jpg')
