"""Public website API: website key required, only published posts, safe product fields."""

from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from cms.models import BlogPost, WebsiteEnquiry
from products.models import Category, Product

from .helpers import png_upload

WEBSITE_KEY = 'test-website-key'


@override_settings(WEBSITE_API_KEY=WEBSITE_KEY)
class PublicBlogApiTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.client.credentials(HTTP_X_WEBSITE_KEY=WEBSITE_KEY)
        self.live = BlogPost.objects.create(
            title='How to choose a sofa stand',
            body='## Height\nPick the right height.',
            tags='sofa stands, legs',
            status=BlogPost.STATUS_PUBLISHED,
            is_featured=True,
            cover_image=png_upload(),
            cover_image_alt='Sofa stand',
        )
        self.older = BlogPost.objects.create(
            title='Zipper sizes',
            body='No. 5 vs No. 10',
            tags='zippers',
            status=BlogPost.STATUS_PUBLISHED,
            published_at=timezone.now() - timedelta(days=3),
        )
        self.draft = BlogPost.objects.create(title='Secret draft', body='hidden')
        self.scheduled = BlogPost.objects.create(
            title='Next week', body='soon', status=BlogPost.STATUS_PUBLISHED,
            published_at=timezone.now() + timedelta(days=7),
        )

    def test_list_is_public_and_only_published_newest_first(self):
        res = self.client.get('/api/public/website/blog/')
        self.assertEqual(res.status_code, 200)
        slugs = [p['slug'] for p in res.data['results']]
        self.assertEqual(slugs, [self.live.slug, self.older.slug])

    def test_list_item_shape_has_no_body_and_absolute_cover(self):
        res = self.client.get('/api/public/website/blog/')
        item = res.data['results'][0]
        self.assertNotIn('body', item)
        self.assertEqual(item['tags'], ['sofa stands', 'legs'])
        self.assertTrue(item['cover_image_url'].startswith('http'))
        self.assertEqual(item['author_name'], 'Omuwenga Suppliers')

    def test_staff_bearer_is_not_the_website_key(self):
        self.client.credentials(HTTP_AUTHORIZATION='Bearer not-a-real-token')
        res = self.client.get('/api/public/website/blog/')
        self.assertEqual(res.status_code, 401)

    def test_bearer_website_key_is_accepted(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {WEBSITE_KEY}')
        res = self.client.get('/api/public/website/blog/')
        self.assertEqual(res.status_code, 200)

    def test_detail_by_slug_includes_body_and_seo_fallbacks(self):
        res = self.client.get(f'/api/public/website/blog/{self.live.slug}/')
        self.assertEqual(res.status_code, 200)
        self.assertIn('## Height', res.data['body'])
        self.assertEqual(res.data['meta_title'], self.live.title)
        self.assertTrue(res.data['meta_description'])

    def test_draft_and_scheduled_posts_are_not_found(self):
        for post in (self.draft, self.scheduled):
            res = self.client.get(f'/api/public/website/blog/{post.slug}/')
            self.assertEqual(res.status_code, 404)

    def test_filters_tag_search_featured(self):
        res = self.client.get('/api/public/website/blog/', {'tag': 'zippers'})
        self.assertEqual([p['slug'] for p in res.data['results']], [self.older.slug])
        res = self.client.get('/api/public/website/blog/', {'search': 'height'})
        self.assertEqual([p['slug'] for p in res.data['results']], [self.live.slug])
        res = self.client.get('/api/public/website/blog/', {'featured': 'true'})
        self.assertEqual([p['slug'] for p in res.data['results']], [self.live.slug])

    def test_public_api_is_read_only(self):
        res = self.client.post('/api/public/website/blog/', {'title': 'x', 'body': 'y'})
        self.assertEqual(res.status_code, 405)


@override_settings(WEBSITE_API_KEY=WEBSITE_KEY)
class PublicCatalogApiTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.client.credentials(HTTP_X_WEBSITE_KEY=WEBSITE_KEY)
        self.zippers = Category.objects.create(name='Zippers')
        self.stands = Category.objects.create(name='Sofa stands')
        self.empty = Category.objects.create(name='Empty category')
        self.no5 = Category.objects.create(name='No. 5', parent=self.zippers)
        self.zip = Product.objects.create(
            name='No. 5 nylon zipper', sku='WEB-ZIP-5', category=self.zippers,
            subcategory=self.no5, price=Decimal('50'), cost=Decimal('20'),
            stock_quantity=30, description='Cushion covers', image=png_upload('zip.png'),
        )
        self.stand = Product.objects.create(
            name='Golden trophy stand', sku='WEB-STAND-1', category=self.stands,
            price=Decimal('400'), cost=Decimal('250'), stock_quantity=0,
        )
        self.service = Product.objects.create(
            name='Upholstery labour', sku='WEB-SVC', category=self.stands,
            price=Decimal('100'), track_stock=False, stock_quantity=0,
        )
        Product.objects.create(
            name='Retired item', sku='WEB-OLD', category=self.zippers,
            price=Decimal('1'), is_active=False,
        )

    def _names(self, res):
        return [p['name'] for p in res.data['results']]

    def test_missing_or_wrong_key_is_rejected(self):
        open_client = APIClient()
        self.assertEqual(open_client.get('/api/public/website/products/').status_code, 401)
        open_client.credentials(HTTP_X_WEBSITE_KEY='wrong-key')
        self.assertEqual(open_client.get('/api/public/website/products/').status_code, 401)
        posted = open_client.post('/api/public/website/enquiries/', {
            'name': 'Amina', 'phone': '0718515142', 'message': 'hello',
        }, format='json')
        self.assertEqual(posted.status_code, 401)
        self.assertEqual(WebsiteEnquiry.objects.count(), 0)

    def test_lists_only_active_products_without_login(self):
        res = self.client.get('/api/public/website/products/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            self._names(res),
            ['No. 5 nylon zipper', 'Golden trophy stand', 'Upholstery labour'],
        )

    def test_never_exposes_cost_stock_or_supplier(self):
        res = self.client.get('/api/public/website/products/')
        for item in res.data['results']:
            for hidden in ('cost', 'stock_quantity', 'supplier', 'supplier_name',
                           'low_stock_threshold', 'price', 'profit_margin'):
                self.assertNotIn(hidden, item)

    def test_in_stock_and_image_url(self):
        res = self.client.get('/api/public/website/products/')
        by_name = {p['name']: p for p in res.data['results']}
        self.assertTrue(by_name['No. 5 nylon zipper']['in_stock'])
        self.assertFalse(by_name['Golden trophy stand']['in_stock'])
        self.assertTrue(by_name['Upholstery labour']['in_stock'])
        self.assertTrue(by_name['No. 5 nylon zipper']['image_url'].startswith('http'))
        self.assertIsNone(by_name['Golden trophy stand']['image_url'])
        self.assertEqual(
            by_name['No. 5 nylon zipper']['subcategory'],
            {'id': self.no5.id, 'name': 'No. 5'},
        )

    @override_settings(WEBSITE_SHOW_PRICES=True)
    def test_price_only_when_enabled(self):
        res = self.client.get('/api/public/website/products/')
        by_name = {p['name']: p for p in res.data['results']}
        self.assertEqual(by_name['No. 5 nylon zipper']['price'], '50.00')

    def test_filter_by_category_subcategory_search_and_image(self):
        res = self.client.get('/api/public/website/products/', {'category': self.stands.id})
        self.assertEqual(self._names(res), ['Golden trophy stand', 'Upholstery labour'])
        res = self.client.get('/api/public/website/products/', {'category': self.no5.id})
        self.assertEqual(self._names(res), ['No. 5 nylon zipper'])
        res = self.client.get('/api/public/website/products/', {'search': 'cushion'})
        self.assertEqual(self._names(res), ['No. 5 nylon zipper'])
        res = self.client.get('/api/public/website/products/', {'has_image': '1'})
        self.assertEqual(self._names(res), ['No. 5 nylon zipper'])

    def test_inactive_product_detail_is_404(self):
        old = Product.objects.get(sku='WEB-OLD')
        self.assertEqual(
            self.client.get(f'/api/public/website/products/{old.id}/').status_code, 404,
        )
        self.assertEqual(
            self.client.get(f'/api/public/website/products/{self.zip.id}/').status_code, 200,
        )

    def test_enquiry_is_saved_and_rejects_a_bad_phone(self):
        res = self.client.post('/api/public/website/enquiries/', {
            'name': 'Amina',
            'phone': '0718 515 142',
            'interest': 'No. 5 nylon zipper',
            'message': '20 metres for cushion covers',
            'product_id': self.zip.id,
        }, format='json')
        self.assertEqual(res.status_code, 201)
        saved = WebsiteEnquiry.objects.get()
        self.assertEqual(saved.product_id, self.zip.id)
        self.assertEqual(saved.status, WebsiteEnquiry.STATUS_NEW)
        bad = self.client.post('/api/public/website/enquiries/', {
            'name': 'A', 'phone': '12', 'message': 'x',
        }, format='json')
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(WebsiteEnquiry.objects.count(), 1)

    def test_honeypot_is_not_stored(self):
        res = self.client.post('/api/public/website/enquiries/', {
            'name': 'Bot', 'phone': '0718000000', 'message': 'buy now',
            'company_website': 'https://spam.example',
        }, format='json')
        self.assertEqual(res.status_code, 201)
        self.assertEqual(WebsiteEnquiry.objects.count(), 0)

    def test_categories_only_with_active_products(self):
        res = self.client.get('/api/public/website/categories/')
        self.assertEqual(res.status_code, 200)
        counts = {c['name']: c['product_count'] for c in res.data}
        self.assertEqual(counts, {'Sofa stands': 2, 'Zippers': 1})
