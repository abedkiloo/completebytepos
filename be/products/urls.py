from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet, ProductViewSet, SizeViewSet,
    ColorViewSet, ProductVariantViewSet, UnitOfMeasureViewSet,
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'sizes', SizeViewSet, basename='size')
router.register(r'colors', ColorViewSet, basename='color')
router.register(r'variants', ProductVariantViewSet, basename='variant')
router.register(r'units', UnitOfMeasureViewSet, basename='product-unit')
router.register(r'', ProductViewSet, basename='product')

urlpatterns = [
    path('', include(router.urls)),
]

