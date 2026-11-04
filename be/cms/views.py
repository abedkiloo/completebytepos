from __future__ import annotations

from django.db.models import Case, Count, IntegerField, Q, Value, When
from rest_framework import generics, mixins, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from products.models import Category, Product
from utils.audit_helpers import log_domain_event
from utils.audit_mixin import AuditedModelViewSetMixin

from .models import BlogPost, WebsiteEnquiry
from .permissions import CanManageWebsite, WebsiteKeyAuthentication
from .serializers import (
    BlogPostAdminSerializer,
    PublicBlogPostDetailSerializer,
    PublicBlogPostListSerializer,
    PublicCategorySerializer,
    PublicEnquirySerializer,
    PublicProductSerializer,
    WebsiteEnquiryAdminSerializer,
)

_TRUTHY = {'1', 'true', 'yes'}


class PublicWebsiteThrottle(AnonRateThrottle):
    scope = 'website_public'
    rate = '240/min'


class PublicEnquiryThrottle(AnonRateThrottle):
    scope = 'website_enquiry'
    rate = '12/hour'


class _PublicReadOnly(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [WebsiteKeyAuthentication]
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
            .annotate(
                image_rank=Case(
                    When(Q(image__isnull=True) | Q(image=''), then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            )
            .order_by('image_rank', 'name')
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


class PublicEnquiryCreateView(generics.CreateAPIView):
    authentication_classes = [WebsiteKeyAuthentication]
    permission_classes = [AllowAny]
    throttle_classes = [PublicEnquiryThrottle]
    serializer_class = PublicEnquirySerializer

    def create(self, request, *args, **kwargs):
        # A filled honeypot is a bot. Pretend it succeeded and store nothing.
        if str(request.data.get('company_website') or '').strip():
            return Response({'status': WebsiteEnquiry.STATUS_NEW}, status=201)
        response = super().create(request, *args, **kwargs)
        if getattr(response, 'status_code', 0) in (200, 201):
            enquiry_id = None
            data = getattr(response, 'data', None)
            if isinstance(data, dict):
                enquiry_id = data.get('id')
            log_domain_event(
                request,
                'create',
                None,
                module='website',
                changes={'enquiry_id': enquiry_id, 'channel': 'public'},
                object_repr='Website enquiry',
            )
        return response


class WebsiteEnquiryAdminViewSet(
    AuditedModelViewSetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = WebsiteEnquiryAdminSerializer
    permission_classes = [IsAuthenticated, CanManageWebsite]
    http_method_names = ['get', 'patch', 'head', 'options']
    audit_module = 'website'

    def get_queryset(self):
        qs = WebsiteEnquiry.objects.select_related('product')
        params = self.request.query_params
        status_filter = (params.get('status') or '').strip()
        if status_filter in {
            WebsiteEnquiry.STATUS_NEW,
            WebsiteEnquiry.STATUS_REVIEWED,
            WebsiteEnquiry.STATUS_CLOSED,
        }:
            qs = qs.filter(status=status_filter)
        search = (params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(phone__icontains=search)
                | Q(interest__icontains=search)
                | Q(message__icontains=search)
                | Q(business__icontains=search)
            )
        return qs


class BlogPostAdminViewSet(
    AuditedModelViewSetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = BlogPostAdminSerializer
    permission_classes = [IsAuthenticated, CanManageWebsite]
    audit_module = 'website'

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
