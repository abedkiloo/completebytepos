from __future__ import annotations

from django.db.models import Count, Q
from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle

from products.models import Category, Product

from .models import BlogPost
from .permissions import CanManageWebsite
from .serializers import (
    BlogPostAdminSerializer,
    PublicBlogPostDetailSerializer,
    PublicBlogPostListSerializer,
    PublicCategorySerializer,
    PublicProductSerializer,
)

_TRUTHY = {'1', 'true', 'yes'}


class PublicWebsiteThrottle(AnonRateThrottle):
    scope = 'website_public'
    rate = '240/min'


class _PublicReadOnly(viewsets.ReadOnlyModelViewSet):
    # No authentication: a stale token from the website must never turn into a 401.
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [PublicWebsiteThrottle]


class PublicBlogPostViewSet(_PublicReadOnly):
    lookup_field = 'slug'

    def get_queryset(self):
        qs = BlogPost.objects.published().select_related('author')
        params = self.request.query_params
        tag = (params.get('tag') or '').strip()
        if tag:
            qs = qs.filter(tags__icontains=tag)
        search = (params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(excerpt__icontains=search)
                | Q(body__icontains=search)
            )
        if (params.get('featured') or '').lower() in _TRUTHY:
            qs = qs.filter(is_featured=True)
        return qs

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return PublicBlogPostDetailSerializer
        return PublicBlogPostListSerializer


class PublicProductViewSet(_PublicReadOnly):
    serializer_class = PublicProductSerializer

    def get_queryset(self):
        qs = (
            Product.objects.filter(is_active=True)
            .select_related('category', 'subcategory')
            .order_by('name')
        )
        params = self.request.query_params
        category = (params.get('category') or '').strip()
        if category.isdigit():
            qs = qs.filter(Q(category_id=category) | Q(subcategory_id=category))
        search = (params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(description__icontains=search)
                | Q(category__name__icontains=search)
                | Q(subcategory__name__icontains=search)
            )
        if (params.get('has_image') or '').lower() in _TRUTHY:
            qs = qs.exclude(image='').exclude(image__isnull=True)
        return qs


class PublicCategoryViewSet(_PublicReadOnly):
    serializer_class = PublicCategorySerializer
    pagination_class = None

    def get_queryset(self):
        active = Q(products__is_active=True)
        return (
            Category.objects.filter(is_active=True)
            .annotate(public_product_count=Count('products', filter=active, distinct=True))
            .filter(public_product_count__gt=0)
            .order_by('name')
        )


class BlogPostAdminViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = BlogPostAdminSerializer
    permission_classes = [IsAuthenticated, CanManageWebsite]

    def get_queryset(self):
        qs = BlogPost.objects.select_related('author').order_by('-updated_at')
        params = self.request.query_params
        status_filter = (params.get('status') or '').strip()
        if status_filter in {BlogPost.STATUS_DRAFT, BlogPost.STATUS_PUBLISHED}:
            qs = qs.filter(status=status_filter)
        search = (params.get('search') or '').strip()
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(tags__icontains=search))
        return qs

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
