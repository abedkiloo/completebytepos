from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PublicBlogPostViewSet, PublicCategoryViewSet, PublicProductViewSet

router = DefaultRouter(trailing_slash=True)
router.include_root_view = False
router.register('blog', PublicBlogPostViewSet, basename='public-blog')
router.register('products', PublicProductViewSet, basename='public-product')
router.register('categories', PublicCategoryViewSet, basename='public-category')

urlpatterns = [path('', include(router.urls))]
