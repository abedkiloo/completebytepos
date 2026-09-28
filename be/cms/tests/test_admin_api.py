"""Blog management API: admins and website.manage holders only."""

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Permission, Role, UserProfile
from accounts.role_definitions import (
    ROLE_MANAGER,
    ROLE_SALES,
    ROLE_SUPER_ADMIN,
    ensure_permissions,
    sync_default_roles,
)
from cms.models import BlogPost
from cms.permissions import user_can_manage_website

from .helpers import png_upload

URL = '/api/cms/blog-posts/'


class BlogAdminApiTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        roles = sync_default_roles()
        cls.admin = User.objects.create_user('cms_admin', password='x', first_name='Ada')
        UserProfile.objects.create(
            user=cls.admin, role='super_admin',
            custom_role=roles[ROLE_SUPER_ADMIN], is_active=True,
        )
        cls.manager = User.objects.create_user('cms_mgr', password='x')
        UserProfile.objects.create(
            user=cls.manager, role='manager',
            custom_role=roles[ROLE_MANAGER], is_active=True,
        )
        cls.cashier = User.objects.create_user('cms_cashier', password='x')
        UserProfile.objects.create(
            user=cls.cashier, role='cashier',
            custom_role=roles[ROLE_SALES], is_active=True,
        )
        writer_role = Role.objects.create(name='Website writer')
        writer_role.permissions.add(
            Permission.objects.get(module='website', action='manage'),
        )
        cls.writer = User.objects.create_user('cms_writer', password='x')
        UserProfile.objects.create(
            user=cls.writer, role='cashier', custom_role=writer_role, is_active=True,
        )

    def _client(self, user=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client

    def test_permission_helper(self):
        self.assertTrue(user_can_manage_website(self.admin))
        self.assertTrue(user_can_manage_website(self.writer))
        self.assertFalse(user_can_manage_website(self.manager))
        self.assertFalse(user_can_manage_website(self.cashier))

    def test_default_roles_do_not_get_website_manage(self):
        for role_name in (ROLE_MANAGER, ROLE_SALES):
            role = Role.objects.get(name=role_name)
            self.assertFalse(role.has_permission('website', 'manage'))

    def test_anonymous_is_401_and_staff_without_grant_is_403(self):
        self.assertEqual(self._client().get(URL).status_code, 401)
        self.assertEqual(self._client(self.cashier).get(URL).status_code, 403)
        self.assertEqual(self._client(self.manager).post(
            URL, {'title': 'x', 'body': 'y'}, format='json',
        ).status_code, 403)

    def test_admin_creates_draft_with_author_and_slug(self):
        res = self._client(self.admin).post(
            URL,
            {'title': 'Webbing 101', 'body': 'Seat support basics', 'tags': 'webbing'},
            format='json',
        )
        self.assertEqual(res.status_code, 201, res.data)
        post = BlogPost.objects.get(pk=res.data['id'])
        self.assertEqual(post.slug, 'webbing-101')
        self.assertEqual(post.author, self.admin)
        self.assertEqual(post.status, BlogPost.STATUS_DRAFT)
        self.assertEqual(res.data['author_name'], 'Ada')

    def test_writer_uploads_cover_and_publishes(self):
        res = self._client(self.writer).post(
            URL,
            {
                'title': 'Castors guide',
                'body': 'Pick castors by load.',
                'status': 'published',
                'cover_image': png_upload(),
                'cover_image_alt': 'Castors',
            },
            format='multipart',
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data['cover_image_url'].startswith('http'))
        self.assertIsNotNone(res.data['published_at'])
        public = self._client().get('/api/public/website/blog/castors-guide/')
        self.assertEqual(public.status_code, 200)

    def test_validation_errors(self):
        client = self._client(self.admin)
        res = client.post(URL, {'title': '  ', 'body': ''}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('title', res.data)
        self.assertIn('body', res.data)
        BlogPost.objects.create(title='Taken', slug='taken', body='x')
        res = client.post(URL, {'title': 'New', 'slug': 'taken', 'body': 'x'}, format='json')
        self.assertEqual(res.status_code, 400)
        self.assertIn('slug', res.data)

    def test_unpublish_hides_post_and_remove_cover(self):
        post = BlogPost.objects.create(
            title='Live post', body='x', status=BlogPost.STATUS_PUBLISHED,
            cover_image=png_upload(),
        )
        client = self._client(self.admin)
        res = client.patch(
            f'{URL}{post.id}/',
            {'status': 'draft', 'remove_cover_image': True},
            format='json',
        )
        self.assertEqual(res.status_code, 200, res.data)
        post.refresh_from_db()
        self.assertIsNone(post.published_at)
        self.assertFalse(post.cover_image)
        self.assertEqual(
            self._client().get(f'/api/public/website/blog/{post.slug}/').status_code, 404,
        )

    def test_blank_slug_on_edit_keeps_existing_url(self):
        post = BlogPost.objects.create(title='Original title', body='x')
        res = self._client(self.admin).patch(
            f'{URL}{post.id}/',
            {'title': 'Renamed title', 'slug': ''},
            format='multipart',
        )
        self.assertEqual(res.status_code, 200, res.data)
        post.refresh_from_db()
        self.assertEqual(post.slug, 'original-title')
        self.assertEqual(post.title, 'Renamed title')

    def test_list_filters_and_delete(self):
        BlogPost.objects.create(title='Draft one', body='x')
        live = BlogPost.objects.create(title='Live one', body='x', status='published')
        client = self._client(self.admin)
        res = client.get(URL, {'status': 'published'})
        self.assertEqual([p['id'] for p in res.data['results']], [live.id])
        self.assertEqual(client.delete(f'{URL}{live.id}/').status_code, 204)
        self.assertFalse(BlogPost.objects.filter(pk=live.id).exists())
