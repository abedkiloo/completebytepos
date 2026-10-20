"""CMS serializer edge-case coverage."""

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory

from accounts.role_definitions import ensure_permissions, sync_default_roles
from cms.models import BlogPost
from cms.serializers import (
    BlogPostAdminSerializer,
    PublicBlogPostDetailSerializer,
    PublicProductSerializer,
    _image_url,
)
from products.models import Product


class CmsSerializersCoverageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.author = User.objects.create_user('cms_ser', password='x', first_name='Pat')

    def test_image_url_value_error_returns_none(self):
        class BrokenField:
            @property
            def url(self):
                raise ValueError('no file')

        class Ser:
            context = {}

        self.assertIsNone(_image_url(Ser(), BrokenField()))
        self.assertIsNone(_image_url(Ser(), None))

    def test_admin_validate_title_body_slug(self):
        ser = BlogPostAdminSerializer()
        with self.assertRaises(ValidationError):
            ser.validate_title('  ')
        with self.assertRaises(ValidationError):
            ser.validate_body('   ')
        self.assertEqual(ser.validate_title(' Ok '), 'Ok')
        self.assertEqual(ser.validate_body(' content '), ' content ')

        BlogPost.objects.create(
            title='Taken', slug='taken-slug', body='x',
            author=self.author, status=BlogPost.STATUS_DRAFT,
        )
        with self.assertRaises(ValidationError):
            ser.validate_slug('taken-slug')
        self.assertEqual(ser.validate_slug('  '), '')
        self.assertEqual(ser.validate_slug('fresh-slug'), 'fresh-slug')

        # blank slug allowed via full serializer (auto-generated later)
        ser = BlogPostAdminSerializer(data={
            'title': 'Fresh',
            'body': 'body text',
            'slug': '  ',
        })
        self.assertTrue(ser.is_valid(), ser.errors)
        self.assertEqual(ser.validated_data.get('slug', ''), '')

    def test_admin_validate_slug_excludes_self(self):
        post = BlogPost.objects.create(
            title='Keep', slug='keep-slug', body='x',
            author=self.author, status=BlogPost.STATUS_DRAFT,
        )
        ser = BlogPostAdminSerializer(
            instance=post,
            data={'title': 'Keep', 'body': 'updated', 'slug': 'keep-slug'},
        )
        self.assertTrue(ser.is_valid(), ser.errors)

    def test_public_meta_fallbacks_and_author(self):
        post = BlogPost.objects.create(
            title='Public', slug='public-post', body='Hello world content',
            excerpt='Short', author=None, status=BlogPost.STATUS_PUBLISHED,
        )
        data = PublicBlogPostDetailSerializer(post).data
        self.assertEqual(data['meta_title'], 'Public')
        self.assertEqual(data['meta_description'], 'Short')
        self.assertEqual(data['author_name'], 'Omuwenga Suppliers')

        post.author = self.author
        post.save(update_fields=['author'])
        data = PublicBlogPostDetailSerializer(post).data
        self.assertEqual(data['author_name'], 'Pat')

    @override_settings(WEBSITE_SHOW_PRICES=True)
    def test_public_product_price_and_no_category(self):
        product = Product.objects.create(
            name='Widget', sku='W-1', price=10, cost=5,
            track_stock=False,
        )
        request = APIRequestFactory().get('/')
        data = PublicProductSerializer(product, context={'request': request}).data
        self.assertEqual(data['price'], str(product.price))
        self.assertIsNone(data['category'])
        self.assertTrue(data['in_stock'])

    def test_admin_author_name_username_fallback(self):
        bare = User.objects.create_user('cms_bare', password='x')
        post = BlogPost.objects.create(
            title='Bare', slug='bare-post', body='x',
            author=bare, status=BlogPost.STATUS_DRAFT,
        )
        data = BlogPostAdminSerializer(post).data
        self.assertEqual(data['author_name'], 'cms_bare')
        post.author = None
        post.save(update_fields=['author'])
        self.assertEqual(BlogPostAdminSerializer(post).data['author_name'], '')
