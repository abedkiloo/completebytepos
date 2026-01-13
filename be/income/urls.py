from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import IncomeCategoryViewSet, IncomeViewSet

router = DefaultRouter()
router.register(r'categories', IncomeCategoryViewSet, basename='income-category')
router.register(r'', IncomeViewSet, basename='income')

urlpatterns = [
    path('', include(router.urls)),
]

