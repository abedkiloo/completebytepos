"""
Comprehensive tests for User Management API
Tests: Create, Read, Update, Delete, List, Search, Role Assignment
"""
from django.test import TransactionTestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .models import UserProfile, Role
from settings.models import Tenant, Branch


class UserAPITestCase(TransactionTestCase):
    """Test cases for User API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        # Create superuser
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123'
        )
        self.superuser_profile = UserProfile.objects.create(
            user=self.superuser,
            role='super_admin',
            is_super_admin=True,
            is_active=True
        )
        
        # Create tenant and branch
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            code='TEST',
            country='Kenya',
            owner=self.superuser,
            created_by=self.superuser
        )
        
        self.branch = Branch.objects.create(
            tenant=self.tenant,
            branch_code='BR001',
            name='Test Branch',
            city='Nairobi',
            country='Kenya',
            is_active=True,
            is_headquarters=True,
            created_by=self.superuser
        )
        
        # Create admin user
        self.admin_user = User.objects.create_user(
            username='admin_user',
            email='admin_user@test.com',
            password='admin123',
            is_staff=True
        )
        self.admin_profile = UserProfile.objects.create(
            user=self.admin_user,
            role='admin',
            is_active=True
        )
        
        # Create regular user
        self.regular_user = User.objects.create_user(
            username='regular_user',
            email='regular@test.com',
            password='user123'
        )
        self.regular_profile = UserProfile.objects.create(
            user=self.regular_user,
            role='cashier',
            is_active=True
        )
        
        # Create role
        self.role = Role.objects.create(
            name='Test Role',
            description='Test role for testing'
        )
        
        # Setup API client
        self.client = APIClient()
    
    def get_auth_token(self, user):
        """Helper to get JWT token for a user"""
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)
    
    def test_list_users_as_superuser(self):
        """Test listing users as superuser"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/accounts/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check if response is paginated
        if 'results' in response.data:
            users = response.data['results']
        else:
            users = response.data
        
        self.assertIsInstance(users, list)
        self.assertGreaterEqual(len(users), 3)  # At least 3 users (superuser, admin, regular)
    
    def test_list_users_as_admin(self):
        """Test listing users as admin"""
        token = self.get_auth_token(self.admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/accounts/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_list_users_as_regular_user(self):
        """Test listing users as regular user (should only see themselves)"""
        token = self.get_auth_token(self.regular_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/accounts/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'results' in response.data:
            users = response.data['results']
        else:
            users = response.data
        
        # Regular user should only see themselves
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]['username'], 'regular_user')
    
    def test_create_user_as_superuser(self):
        """Test creating a new user as superuser"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        user_data = {
            'username': 'new_user',
            'email': 'new_user@test.com',
            'password': 'newpass123',
            'first_name': 'New',
            'last_name': 'User',
            'is_active': True,
            'is_staff': False,
            'role': 'cashier',
            'phone_number': '254712345678'
        }
        
        response = self.client.post('/api/accounts/users/', user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify user was created
        self.assertTrue(User.objects.filter(username='new_user').exists())
        user = User.objects.get(username='new_user')
        self.assertTrue(user.check_password('newpass123'))
        self.assertIsNotNone(user.profile)
        self.assertEqual(user.profile.role, 'cashier')
    
    def test_create_user_as_admin(self):
        """Test creating a new user as admin"""
        token = self.get_auth_token(self.admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        user_data = {
            'username': 'admin_created_user',
            'email': 'admin_created@test.com',
            'password': 'pass123',
            'first_name': 'Admin',
            'last_name': 'Created',
            'role': 'manager'
        }
        
        response = self.client.post('/api/accounts/users/', user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username='admin_created_user').exists())
    
    def test_create_user_as_regular_user_forbidden(self):
        """Test that regular users cannot create users"""
        token = self.get_auth_token(self.regular_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        user_data = {
            'username': 'unauthorized_user',
            'email': 'unauthorized@test.com',
            'password': 'pass123',
            'role': 'cashier'
        }
        
        response = self.client.post('/api/accounts/users/', user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_update_user(self):
        """Test updating a user"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        update_data = {
            'first_name': 'Updated',
            'last_name': 'Name',
            'email': 'updated@test.com',
            'is_active': True
        }
        
        response = self.client.put(f'/api/accounts/users/{self.regular_user.id}/', update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify update
        self.regular_user.refresh_from_db()
        self.assertEqual(self.regular_user.first_name, 'Updated')
        self.assertEqual(self.regular_user.email, 'updated@test.com')
    
    def test_delete_user(self):
        """Test deleting a user"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Create a user to delete
        user_to_delete = User.objects.create_user(
            username='to_delete',
            email='delete@test.com',
            password='pass123'
        )
        user_id = user_to_delete.id
        
        response = self.client.delete(f'/api/accounts/users/{user_id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify deletion
        self.assertFalse(User.objects.filter(id=user_id).exists())
    
    def test_assign_role(self):
        """Test assigning a role to a user"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.post(
            f'/api/accounts/users/{self.regular_user.id}/assign_role/',
            {'role_id': self.role.id},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify role assignment
        self.regular_user.profile.refresh_from_db()
        self.assertEqual(self.regular_user.profile.custom_role, self.role)
    
    def test_search_users(self):
        """Test searching users"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/accounts/users/search/?q=regular')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        users = response.data
        self.assertIsInstance(users, list)
        self.assertGreater(len(users), 0)
        # Should find regular_user
        usernames = [u['username'] for u in users]
        self.assertIn('regular_user', usernames)
    
    def test_user_validation(self):
        """Test user creation validation"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Try to create user without required fields
        invalid_data = {
            'email': 'invalid@test.com'
            # Missing username and password
        }
        
        response = self.client.post('/api/accounts/users/', invalid_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_duplicate_username(self):
        """Test that duplicate usernames are rejected"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        user_data = {
            'username': 'regular_user',  # Already exists
            'email': 'duplicate@test.com',
            'password': 'pass123',
            'role': 'cashier'
        }
        
        response = self.client.post('/api/accounts/users/', user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_user_profile_creation(self):
        """Test that user profile is created automatically"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        user_data = {
            'username': 'profile_test',
            'email': 'profile@test.com',
            'password': 'pass123',
            'role': 'manager',
            'phone_number': '254798765432'
        }
        
        response = self.client.post('/api/accounts/users/', user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        user = User.objects.get(username='profile_test')
        self.assertIsNotNone(user.profile)
        self.assertEqual(user.profile.role, 'manager')
        self.assertEqual(user.profile.phone_number, '254798765432')
    
    def test_list_users_pagination(self):
        """Test that user list supports pagination"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Request with page_size
        response = self.client.get('/api/accounts/users/?page_size=2')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should have pagination metadata if paginated
        if 'results' in response.data:
            self.assertIn('count', response.data)
            self.assertIn('next', response.data)
            self.assertIn('previous', response.data)
            self.assertIsInstance(response.data['results'], list)
    
    def test_user_list_after_create(self):
        """Test that newly created user appears in list"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Get initial count
        initial_response = self.client.get('/api/accounts/users/')
        if 'results' in initial_response.data:
            initial_count = len(initial_response.data['results'])
        else:
            initial_count = len(initial_response.data)
        
        # Create new user
        user_data = {
            'username': 'list_test_user',
            'email': 'list_test@test.com',
            'password': 'pass123',
            'role': 'cashier'
        }
        create_response = self.client.post('/api/accounts/users/', user_data, format='json')
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        
        # List users again
        list_response = self.client.get('/api/accounts/users/')
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        
        if 'results' in list_response.data:
            users = list_response.data['results']
        else:
            users = list_response.data
        
        # Should have one more user
        self.assertGreaterEqual(len(users), initial_count + 1)
        
        # New user should be in the list
        usernames = [u['username'] for u in users]
        self.assertIn('list_test_user', usernames)
    
    def test_get_user(self):
        """Test retrieving a single user"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get(f'/api/accounts/users/{self.regular_user.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'regular_user')
    
    def test_change_password(self):
        """Test changing user password"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.post(
            f'/api/accounts/users/{self.regular_user.id}/change_password/',
            {'new_password': 'newpass123'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify password changed
        self.regular_user.refresh_from_db()
        self.assertTrue(self.regular_user.check_password('newpass123'))
    
    def test_change_own_password(self):
        """Test user changing their own password"""
        token = self.get_auth_token(self.regular_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.post(
            f'/api/accounts/users/{self.regular_user.id}/change_password/',
            {'new_password': 'mynewpass123'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.regular_user.refresh_from_db()
        self.assertTrue(self.regular_user.check_password('mynewpass123'))
    
    def test_update_own_profile(self):
        """Test user updating their own profile"""
        token = self.get_auth_token(self.regular_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        update_data = {
            'first_name': 'My',
            'last_name': 'Name',
            'email': 'myemail@test.com'
        }
        
        response = self.client.put(
            f'/api/accounts/users/{self.regular_user.id}/',
            update_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.regular_user.refresh_from_db()
        self.assertEqual(self.regular_user.first_name, 'My')
        self.assertEqual(self.regular_user.email, 'myemail@test.com')
    
    def test_partial_update_user(self):
        """Test partial update (PATCH) of user"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.patch(
            f'/api/accounts/users/{self.regular_user.id}/',
            {'first_name': 'Patched'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.regular_user.refresh_from_db()
        self.assertEqual(self.regular_user.first_name, 'Patched')
    
    def test_delete_user_as_admin_forbidden(self):
        """Test that admin cannot delete users"""
        token = self.get_auth_token(self.admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        user_to_delete = User.objects.create_user(
            username='to_delete_admin',
            email='delete_admin@test.com',
            password='pass123'
        )
        
        response = self.client.delete(f'/api/accounts/users/{user_to_delete.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_assign_role_invalid_role(self):
        """Test assigning invalid role"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.post(
            f'/api/accounts/users/{self.regular_user.id}/assign_role/',
            {'role_id': 99999},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_assign_role_missing_role_id(self):
        """Test assigning role without role_id"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.post(
            f'/api/accounts/users/{self.regular_user.id}/assign_role/',
            {},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_login(self):
        """Test user login"""
        response = self.client.post(
            '/api/accounts/auth/login/',
            {'username': 'regular_user', 'password': 'user123'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = self.client.post(
            '/api/accounts/auth/login/',
            {'username': 'regular_user', 'password': 'wrongpass'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_logout(self):
        """Test user logout"""
        token = self.get_auth_token(self.regular_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        refresh = RefreshToken.for_user(self.regular_user)
        response = self.client.post(
            '/api/accounts/auth/logout/',
            {'refresh': str(refresh)},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_me_endpoint(self):
        """Test getting current user info"""
        token = self.get_auth_token(self.regular_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/accounts/auth/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['username'], 'regular_user')
        self.assertIn('profile', response.data)
    
    def test_list_permissions(self):
        """Test listing permissions"""
        from .models import Permission
        
        # Create a permission
        permission = Permission.objects.create(
            module='products',
            action='view',
            description='View products'
        )
        
        token = self.get_auth_token(self.admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/accounts/permissions/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_permissions_by_module(self):
        """Test getting permissions grouped by module"""
        from .models import Permission
        
        Permission.objects.create(module='products', action='view')
        Permission.objects.create(module='products', action='create')
        Permission.objects.create(module='sales', action='view')
        
        token = self.get_auth_token(self.admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/accounts/permissions/by_module/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Products', response.data)
    
    def test_list_roles(self):
        """Test listing roles"""
        token = self.get_auth_token(self.regular_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get('/api/accounts/roles/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_create_role(self):
        """Test creating a role"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        role_data = {
            'name': 'New Role',
            'description': 'A new role',
            'is_active': True
        }
        
        response = self.client.post('/api/accounts/roles/', role_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Role.objects.filter(name='New Role').exists())
    
    def test_create_role_as_admin_forbidden(self):
        """Test that admin cannot create roles"""
        token = self.get_auth_token(self.admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        role_data = {'name': 'Unauthorized Role'}
        response = self.client.post('/api/accounts/roles/', role_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_update_role(self):
        """Test updating a role"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        update_data = {'name': 'Updated Role', 'description': 'Updated description'}
        response = self.client.put(
            f'/api/accounts/roles/{self.role.id}/',
            update_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.role.refresh_from_db()
        self.assertEqual(self.role.name, 'Updated Role')
    
    def test_delete_role(self):
        """Test deleting a role"""
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        role_to_delete = Role.objects.create(name='To Delete')
        response = self.client.delete(f'/api/accounts/roles/{role_to_delete.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Role.objects.filter(id=role_to_delete.id).exists())
    
    def test_assign_permissions_to_role(self):
        """Test assigning permissions to a role"""
        from .models import Permission
        
        permission1 = Permission.objects.create(module='products', action='view')
        permission2 = Permission.objects.create(module='products', action='create')
        
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.post(
            f'/api/accounts/roles/{self.role.id}/assign_permissions/',
            {'permission_ids': [permission1.id, permission2.id]},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.role.refresh_from_db()
        self.assertEqual(self.role.permissions.count(), 2)
    
    def test_get_role_users(self):
        """Test getting users with a specific role"""
        self.regular_user.profile.custom_role = self.role
        self.regular_user.profile.save()
        
        token = self.get_auth_token(self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get(f'/api/accounts/roles/{self.role.id}/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('users', response.data)
        self.assertGreater(len(response.data['users']), 0)
    
    def test_get_role(self):
        """Test retrieving a single role"""
        token = self.get_auth_token(self.regular_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        response = self.client.get(f'/api/accounts/roles/{self.role.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Role')
