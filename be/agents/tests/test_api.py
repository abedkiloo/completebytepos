"""Agents API + finalize hard rules."""

import io
import uuid

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import Role, UserProfile
from accounts.role_definitions import (
    ROLE_FIELD_AGENT,
    ROLE_SALES,
    ensure_permissions,
    sync_default_roles,
)
from agents.models import CustomerSite, SiteMedia
from agents.services import SiteFinalizeError, assert_can_finalize, finalize_site
from sales.models import Customer


def _png(name='site.png'):
    buf = io.BytesIO()
    Image.new('RGB', (32, 32), color=(20, 160, 80)).save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


class AgentAPITestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_permissions()
        sync_default_roles()
        cls.agent_user = User.objects.create_user(username='field_agent', password='a')
        cls.agent_role = Role.objects.get(name=ROLE_FIELD_AGENT)
        UserProfile.objects.create(
            user=cls.agent_user,
            role='cashier',
            custom_role=cls.agent_role,
            is_active=True,
        )
        cls.sales_user = User.objects.create_user(username='sales_no_agent', password='a')
        cls.sales_role = Role.objects.get(name=ROLE_SALES)
        UserProfile.objects.create(
            user=cls.sales_user,
            role='cashier',
            custom_role=cls.sales_role,
            is_active=True,
        )
        cls.customer = Customer.objects.create(name='Site Cust', phone='0700')

    def setUp(self):
        token = RefreshToken.for_user(self.agent_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def test_cannot_finalize_without_lat_lng(self):
        site = CustomerSite.objects.create(
            customer=self.customer,
            created_by=self.agent_user,
        )
        SiteMedia.objects.create(site=site, image=_png(), created_by=self.agent_user)
        with self.assertRaises(SiteFinalizeError):
            assert_can_finalize(site)
        res = self.client.post(f'/api/agents/sites/{site.id}/finalize/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('location', res.data)

    def test_cannot_finalize_without_media(self):
        site = CustomerSite.objects.create(
            customer=self.customer,
            latitude='-1.2921000',
            longitude='36.8219000',
            created_by=self.agent_user,
        )
        res = self.client.post(f'/api/agents/sites/{site.id}/finalize/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('media', res.data)

    def test_cannot_finalize_without_customer(self):
        site = CustomerSite.objects.create(
            latitude='-1.2921000',
            longitude='36.8219000',
            created_by=self.agent_user,
        )
        SiteMedia.objects.create(site=site, image=_png(), created_by=self.agent_user)
        res = self.client.post(f'/api/agents/sites/{site.id}/finalize/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('customer', res.data)

    def test_finalize_success_flow(self):
        create = self.client.post(
            '/api/agents/sites/',
            {
                'customer': self.customer.id,
                'label': 'Gate A',
                'latitude': '-1.2921',
                'longitude': '36.8219',
                'accuracy': 12.5,
                'landmark': 'Blue container',
                'client_uuid': str(uuid.uuid4()),
            },
            format='json',
        )
        self.assertEqual(create.status_code, status.HTTP_201_CREATED, create.data)
        site_id = create.data['id']

        upload = self.client.post(
            f'/api/agents/sites/{site_id}/media/',
            {'image': _png(), 'caption': 'Entrance'},
            format='multipart',
        )
        self.assertEqual(upload.status_code, status.HTTP_201_CREATED, upload.data)

        fin = self.client.post(f'/api/agents/sites/{site_id}/finalize/')
        self.assertEqual(fin.status_code, status.HTTP_200_OK, fin.data)
        self.assertEqual(fin.data['status'], 'finalized')
        self.assertTrue(fin.data['has_pin'])
        self.assertGreaterEqual(fin.data['media_count'], 1)

    def test_sales_role_denied_agents_api(self):
        token = RefreshToken.for_user(self.sales_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        res = self.client.get('/api/agents/sites/')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_field_agent_role_has_agents_permissions(self):
        self.assertTrue(
            self.agent_user.profile.has_permission('agents', 'view'),
        )
        self.assertTrue(
            self.agent_user.profile.has_permission('agents', 'create'),
        )
        self.assertTrue(
            self.agent_user.profile.has_permission('agents', 'update'),
        )
        self.assertFalse(
            self.sales_user.profile.has_permission('agents', 'view'),
        )

    def test_list_filter_and_config(self):
        CustomerSite.objects.create(
            customer=self.customer,
            latitude='-1.2',
            longitude='36.8',
            status=CustomerSite.STATUS_DRAFT,
            created_by=self.agent_user,
        )
        listed = self.client.get(
            f'/api/agents/sites/?customer={self.customer.id}&status=draft',
        )
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(listed.data), 1)

        cfg = self.client.get('/api/agents/sites/config/')
        self.assertEqual(cfg.status_code, status.HTTP_200_OK)
        self.assertEqual(cfg.data['min_site_media'], 1)

    def test_media_list_and_delete(self):
        site = CustomerSite.objects.create(
            customer=self.customer,
            latitude='-1.2',
            longitude='36.8',
            created_by=self.agent_user,
        )
        m1 = SiteMedia.objects.create(site=site, image=_png('a.png'), created_by=self.agent_user)
        SiteMedia.objects.create(site=site, image=_png('b.png'), created_by=self.agent_user)
        listed = self.client.get(f'/api/agents/sites/{site.id}/media/')
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(len(listed.data), 2)

        deleted = self.client.delete(f'/api/agents/sites/{site.id}/media/{m1.id}/')
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)

    def test_cannot_delete_last_media_when_finalized(self):
        site = CustomerSite.objects.create(
            customer=self.customer,
            latitude='-1.2',
            longitude='36.8',
            created_by=self.agent_user,
        )
        media = SiteMedia.objects.create(site=site, image=_png(), created_by=self.agent_user)
        finalize_site(site)
        res = self.client.delete(f'/api/agents/sites/{site.id}/media/{media.id}/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_site_and_str(self):
        site = CustomerSite.objects.create(
            customer=self.customer,
            label='Yard',
            latitude='-1.2',
            longitude='36.8',
            created_by=self.agent_user,
        )
        self.assertIn('Yard', str(site))
        media = SiteMedia.objects.create(site=site, image=_png(), created_by=self.agent_user)
        self.assertIn('Media', str(media))

        patched = self.client.patch(
            f'/api/agents/sites/{site.id}/',
            {'landmark': 'Near mango tree'},
            format='json',
        )
        self.assertEqual(patched.status_code, status.HTTP_200_OK)
        self.assertEqual(patched.data['landmark'], 'Near mango tree')

    def test_delete_missing_media_404(self):
        site = CustomerSite.objects.create(
            customer=self.customer,
            latitude='-1.2',
            longitude='36.8',
            created_by=self.agent_user,
        )
        res = self.client.delete(f'/api/agents/sites/{site.id}/media/99999/')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_finalized_cannot_clear_pin(self):
        site = CustomerSite.objects.create(
            customer=self.customer,
            latitude='-1.2',
            longitude='36.8',
            created_by=self.agent_user,
        )
        SiteMedia.objects.create(site=site, image=_png(), created_by=self.agent_user)
        finalize_site(site)
        res = self.client.patch(
            f'/api/agents/sites/{site.id}/',
            {'latitude': None, 'longitude': None},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_media_upload_validation_edges(self):
        from agents.config import MAX_SITE_IMAGE_BYTES, MAX_SITE_MEDIA
        from agents.serializers import SiteMediaSerializer, SiteMediaUploadSerializer

        site = CustomerSite.objects.create(
            customer=self.customer,
            latitude='-1.2',
            longitude='36.8',
            created_by=self.agent_user,
        )
        media = SiteMedia.objects.create(site=site, image=_png(), created_by=self.agent_user)
        relative = SiteMediaSerializer(media).data['image_url']
        self.assertTrue(relative.startswith('/') or 'site_media' in relative)

        upload = SiteMediaUploadSerializer(
            data={'image': None},
            context={'site': site, 'request': None},
        )
        self.assertFalse(upload.is_valid())

        huge = SimpleUploadedFile(
            'huge.png',
            b'x' * (MAX_SITE_IMAGE_BYTES * 10 + 1),
            content_type='image/png',
        )
        oversized = SiteMediaUploadSerializer(
            data={'image': huge},
            context={'site': site},
        )
        self.assertFalse(oversized.is_valid())

        for i in range(MAX_SITE_MEDIA - site.media.count()):
            SiteMedia.objects.create(
                site=site, image=_png(f'f{i}.png'), created_by=self.agent_user,
            )
        blocked = self.client.post(
            f'/api/agents/sites/{site.id}/media/',
            {'image': _png('overflow.png')},
            format='multipart',
        )
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_and_destroy_site(self):
        site = CustomerSite.objects.create(
            customer=self.customer,
            latitude='-1.2',
            longitude='36.8',
            label='',
            created_by=self.agent_user,
        )
        self.assertIn('Site', str(site))
        detail = self.client.get(f'/api/agents/sites/{site.id}/')
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        deleted = self.client.delete(f'/api/agents/sites/{site.id}/')
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
