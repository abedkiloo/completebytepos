from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import path
from django.http import JsonResponse, HttpResponse

from idempotency.middleware import IdempotencyMiddleware
from idempotency.models import IdempotencyRecord


def _echo(request):
    return JsonResponse({'ok': True, 'echo': request.body.decode('utf-8')}, status=201)


def _unauthorized(request):
    return HttpResponse('auth required', status=401)


urlpatterns = [
    path('api/test-idempotent/', _echo),
    path('api/test-idempotent-401/', _unauthorized),
]


@override_settings(ROOT_URLCONF='idempotency.tests')
class IdempotencyMiddlewareTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='sales', password='x')
        self.client = Client()

    def test_replays_same_key(self):
        headers = {'HTTP_IDEMPOTENCY_KEY': 'k-1'}
        r1 = self.client.post(
            '/api/test-idempotent/',
            data='{"a":1}',
            content_type='application/json',
            **headers,
        )
        self.assertEqual(r1.status_code, 201)
        self.assertNotEqual(r1.get('X-Idempotency-Replayed'), 'true')

        r2 = self.client.post(
            '/api/test-idempotent/',
            data='{"a":1}',
            content_type='application/json',
            **headers,
        )
        self.assertEqual(r2.status_code, 201)
        self.assertEqual(r2.get('X-Idempotency-Replayed'), 'true')
        self.assertEqual(r1.content, r2.content)
        self.assertEqual(IdempotencyRecord.objects.count(), 1)

    def test_conflict_on_body_mismatch(self):
        headers = {'HTTP_IDEMPOTENCY_KEY': 'k-2'}
        self.client.post(
            '/api/test-idempotent/',
            data='{"a":1}',
            content_type='application/json',
            **headers,
        )
        r = self.client.post(
            '/api/test-idempotent/',
            data='{"a":2}',
            content_type='application/json',
            **headers,
        )
        self.assertEqual(r.status_code, 409)

    def test_without_key_passes_through(self):
        r1 = self.client.post(
            '/api/test-idempotent/',
            data='{}',
            content_type='application/json',
        )
        r2 = self.client.post(
            '/api/test-idempotent/',
            data='{}',
            content_type='application/json',
        )
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        self.assertEqual(IdempotencyRecord.objects.count(), 0)

    def test_get_ignored_and_401_not_cached(self):
        r = self.client.get('/api/test-idempotent/', HTTP_IDEMPOTENCY_KEY='g-1')
        self.assertNotEqual(r.status_code, 500)
        self.assertEqual(IdempotencyRecord.objects.count(), 0)

        r401 = self.client.post(
            '/api/test-idempotent-401/',
            data='{}',
            content_type='application/json',
            HTTP_IDEMPOTENCY_KEY='auth-1',
        )
        self.assertEqual(r401.status_code, 401)
        self.assertEqual(IdempotencyRecord.objects.count(), 0)

    def test_model_str(self):
        rec = IdempotencyRecord.objects.create(
            key='k',
            method='POST',
            path='/api/x/',
            status_code=201,
            response_body='{}',
        )
        self.assertIn('POST', str(rec))
        self.assertIn('k', str(rec))

    def test_process_response_non_idempotent_method_guard(self):
        factory = RequestFactory()
        request = factory.get('/api/x/')
        request._idempotency_key = 'ghost'  # noqa: SLF001
        mw = IdempotencyMiddleware(lambda req: HttpResponse('ok'))
        response = mw.process_response(request, HttpResponse('ok'))
        self.assertEqual(response.content, b'ok')
        self.assertEqual(IdempotencyRecord.objects.count(), 0)
