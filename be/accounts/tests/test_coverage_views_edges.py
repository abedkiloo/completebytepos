"""High-value accounts/views.py edges still missing from prior coverage."""

from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import Role, UserProfile
from accounts.role_definitions import ROLE_MANAGER, ensure_permissions, sync_default_roles
from accounts.views import PermissionViewSet, RoleViewSet, UserViewSet
from utils.tests.api_test_base import ManagerAPITestCase, SuperAdminAPITestCase


class PermissionRoleQuerysetGaps(SuperAdminAPITestCase):
    def test_permission_queryset_no_request_and_exception(self):
        view = PermissionViewSet()
        # No request → empty queryset branch
        qs = view.get_queryset()
        self.assertEqual(qs.count(), 0)

        factory = APIRequestFactory()
        req = factory.get('/')
        force_authenticate(req, user=self.admin)
        view.request = Request(req)
        view.request.user = self.admin
        with patch('accounts.views._user_can_manage_permissions', side_effect=RuntimeError('boom')):
            qs2 = view.get_queryset()
            self.assertEqual(qs2.count(), 0)

    def test_permission_list_unpaginated(self):
        view = PermissionViewSet()
        factory = APIRequestFactory()
        req = factory.get('/')
        force_authenticate(req, user=self.admin)
        request = Request(req)
        request.user = self.admin
        view.request = request
        view.format_kwarg = None
        view.action = 'list'
        view.args = ()
        view.kwargs = {}
        with patch.object(view, 'paginate_queryset', return_value=None):
            with patch.object(view, 'filter_queryset', return_value=view.get_queryset()):
                resp = view.list(request)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_permission_by_module_denied_for_manager(self):
        ensure_permissions()
        roles = sync_default_roles()
        mgr = User.objects.create_user('perm_mgr_edge', password='x')
        UserProfile.objects.create(
            user=mgr, role='manager', custom_role=roles[ROLE_MANAGER], is_active=True,
        )
        view = PermissionViewSet.as_view({'get': 'by_module'})
        factory = APIRequestFactory()
        req = factory.get('/api/accounts/permissions/by_module/')
        force_authenticate(req, user=mgr)
        resp = view(req)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

        with patch('accounts.views._user_can_manage_permissions', side_effect=RuntimeError('x')):
            resp2 = view(req)
            self.assertEqual(resp2.status_code, status.HTTP_403_FORBIDDEN)

        view_dom = PermissionViewSet.as_view({'get': 'by_domain'})
        req_dom = factory.get('/api/accounts/permissions/by_domain/')
        force_authenticate(req_dom, user=mgr)
        self.assertEqual(view_dom(req_dom).status_code, status.HTTP_403_FORBIDDEN)
        with patch('accounts.views._user_can_manage_permissions', side_effect=RuntimeError('x')):
            self.assertEqual(view_dom(req_dom).status_code, status.HTTP_403_FORBIDDEN)

    def test_role_queryset_no_request_and_exception(self):
        view = RoleViewSet()
        qs = view.get_queryset()
        self.assertEqual(qs.count(), 0)

        factory = APIRequestFactory()
        req = factory.get('/')
        force_authenticate(req, user=self.admin)
        view.request = Request(req)
        view.request.user = self.admin
        with patch.object(Role.objects, 'all', side_effect=RuntimeError('role boom')):
            qs2 = view.get_queryset()
            self.assertEqual(qs2.count(), 0)

    def test_role_list_unpaginated_and_edit_disabled(self):
        view = RoleViewSet()
        factory = APIRequestFactory()
        req = factory.get('/')
        force_authenticate(req, user=self.admin)
        request = Request(req)
        request.user = self.admin
        view.request = request
        view.format_kwarg = None
        view.action = 'list'
        view.args = ()
        view.kwargs = {}
        with patch.object(view, 'paginate_queryset', return_value=None):
            with patch.object(view, 'filter_queryset', side_effect=lambda qs: qs):
                with patch.object(view, 'get_queryset', return_value=Role.objects.all()):
                    resp = view.list(request)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        with patch('accounts.views.users_enable_role_edit', return_value=False):
            role = Role.objects.first()
            upd = RoleViewSet.as_view({'patch': 'partial_update'})
            preq = factory.patch(f'/api/accounts/roles/{role.pk}/', {'name': role.name}, format='json')
            force_authenticate(preq, user=self.admin)
            self.assertEqual(upd(preq, pk=role.pk).status_code, status.HTTP_403_FORBIDDEN)


class UserViewEdges(ManagerAPITestCase):
    def test_create_serializer_class_and_list_unpaginated(self):
        view = UserViewSet()
        view.action = 'create'
        from accounts.serializers import UserCreateSerializer
        self.assertIs(view.get_serializer_class(), UserCreateSerializer)

        factory = APIRequestFactory()
        req = factory.get('/')
        force_authenticate(req, user=self.manager_user)
        request = Request(req)
        request.user = self.manager_user
        view.request = request
        view.format_kwarg = None
        view.action = 'list'
        view.args = ()
        view.kwargs = {}
        with patch.object(view, 'paginate_queryset', return_value=None):
            with patch.object(view, 'filter_queryset', side_effect=lambda qs: qs):
                with patch.object(view, 'get_queryset', return_value=User.objects.filter(pk=self.manager_user.pk)):
                    resp = view.list(request)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_logout_blacklist_and_failure(self):
        from accounts.views import AuthViewSet

        view = AuthViewSet.as_view({'post': 'logout'})
        factory = APIRequestFactory()
        req = factory.post('/api/accounts/auth/logout/', {'refresh': 'invalid-token'}, format='json')
        force_authenticate(req, user=self.manager_user)
        resp = view(req)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        with patch('utils.audit.log_audit', side_effect=RuntimeError('logout boom')):
            req2 = factory.post('/api/accounts/auth/logout/', {}, format='json')
            force_authenticate(req2, user=self.manager_user)
            resp2 = view(req2)
            self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_me_profile_exception(self):
        from accounts.views import AuthViewSet

        view = AuthViewSet.as_view({'get': 'me'})
        factory = APIRequestFactory()
        req = factory.get('/api/accounts/auth/me/')
        force_authenticate(req, user=self.manager_user)
        with patch('accounts.views.UserProfileSerializer', side_effect=RuntimeError('me boom')):
            resp = view(req)
            # Still returns 200 with empty profile/permissions on exception
            self.assertEqual(resp.status_code, status.HTTP_200_OK)
