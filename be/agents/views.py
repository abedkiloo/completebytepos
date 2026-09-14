from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.permissions import RequirePermPerAction

from .config import MAX_SITE_IMAGE_BYTES, MAX_SITE_MEDIA, MIN_SITE_MEDIA
from .models import CustomerSite, SiteMedia
from .serializers import (
    CustomerSiteSerializer,
    SiteConfigSerializer,
    SiteFinalizeSerializer,
    SiteMediaSerializer,
    SiteMediaUploadSerializer,
)
from .services import SiteFinalizeError

AGENTS_PERMS = RequirePermPerAction(
    'agents',
    {
        'list': 'view',
        'retrieve': 'view',
        'create': 'create',
        'update': 'update',
        'partial_update': 'update',
        'destroy': 'update',
        'finalize': 'update',
        'media': 'update',
        'media_detail': 'update',
        'config': 'view',
    },
)


class CustomerSiteViewSet(viewsets.ModelViewSet):
    queryset = CustomerSite.objects.select_related('customer', 'created_by').prefetch_related(
        'media',
    )
    serializer_class = CustomerSiteSerializer
    permission_classes = [IsAuthenticated, AGENTS_PERMS]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = super().get_queryset()
        customer_id = self.request.query_params.get('customer')
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    @action(detail=False, methods=['get'], url_path='config')
    def config(self, request):
        data = SiteConfigSerializer({
            'min_site_media': MIN_SITE_MEDIA,
            'max_site_media': MAX_SITE_MEDIA,
            'max_site_image_bytes': MAX_SITE_IMAGE_BYTES,
        }).data
        return Response(data)

    @action(detail=True, methods=['post'], url_path='finalize')
    def finalize(self, request, pk=None):
        site = self.get_object()
        serializer = SiteFinalizeSerializer(
            data=request.data or {},
            context={'site': site, 'request': request},
        )
        try:
            serializer.is_valid(raise_exception=True)
            site = serializer.save()
        except SiteFinalizeError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            CustomerSiteSerializer(site, context={'request': request}).data,
        )

    @action(
        detail=True,
        methods=['get', 'post'],
        url_path='media',
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def media(self, request, pk=None):
        site = self.get_object()
        if request.method == 'GET':
            ser = SiteMediaSerializer(
                site.media.all(), many=True, context={'request': request},
            )
            return Response(ser.data)

        upload = SiteMediaUploadSerializer(
            data=request.data,
            context={'site': site, 'request': request},
        )
        upload.is_valid(raise_exception=True)
        media = upload.save()
        return Response(
            SiteMediaSerializer(media, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=['delete'],
        url_path=r'media/(?P<media_id>[^/.]+)',
    )
    def media_detail(self, request, pk=None, media_id=None):
        site = self.get_object()
        try:
            media = site.media.get(pk=media_id)
        except SiteMedia.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if site.status == CustomerSite.STATUS_FINALIZED and site.media.count() <= MIN_SITE_MEDIA:
            return Response(
                {'media': 'Cannot remove the last required photo from a finalized site.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        media.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
