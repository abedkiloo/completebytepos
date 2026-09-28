from django.test import SimpleTestCase, TestCase, override_settings
from pathlib import Path

from django.conf import settings

from config.media_urls import absolute_media_url
from config.urls import media_urlpatterns


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


class ServeMediaUrlTests(SimpleTestCase):
    @override_settings(DEBUG=False, SERVE_MEDIA=True, MEDIA_URL='/media/')
    def test_debug_off_still_registers_media_route(self):
        patterns = media_urlpatterns()
        self.assertEqual(len(patterns), 1)

    @override_settings(DEBUG=False)
    def test_django_static_helper_does_not_register_routes_when_debug_off(self):
        from django.conf.urls.static import static as django_static

        self.assertEqual(django_static('/media/', document_root='/tmp'), [])

    @override_settings(DEBUG=False, SERVE_MEDIA=False)
    def test_media_route_can_be_disabled(self):
        self.assertEqual(media_urlpatterns(), [])


class ServeUploadedMediaTests(TestCase):
    def test_jpeg_is_returned_from_media_root(self):
        dest = Path(settings.MEDIA_ROOT) / 'products'
        dest.mkdir(parents=True, exist_ok=True)
        (dest / 'probe.jpeg').write_bytes(b'\xff\xd8\xff\xdb')
        response = self.client.get('/media/products/probe.jpeg')
        self.assertEqual(response.status_code, 200)
