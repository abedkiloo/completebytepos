from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BlogPostAdminViewSet

router = DefaultRouter(trailing_slash=True)
router.include_root_view = False
router.register('blog-posts', BlogPostAdminViewSet, basename='cms-blog-post')

urlpatterns = [path('', include(router.urls))]
