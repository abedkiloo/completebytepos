from rest_framework import serializers

from .config import MAX_SITE_MEDIA, MAX_SITE_IMAGE_BYTES, MIN_SITE_MEDIA
from .models import CustomerSite, SiteMedia
from .services import assert_can_finalize, finalize_site


class SiteMediaSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = SiteMedia
        fields = (
            'id', 'site', 'image', 'image_url', 'caption',
            'created_by', 'client_uuid', 'created_at',
        )
        read_only_fields = ('id', 'site', 'created_by', 'created_at', 'image_url')

    def get_image_url(self, obj):
        request = self.context.get('request')
        url = obj.image.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url


class CustomerSiteSerializer(serializers.ModelSerializer):
    media = SiteMediaSerializer(many=True, read_only=True)
    media_count = serializers.IntegerField(read_only=True)
    has_pin = serializers.BooleanField(read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True, default=None)
    min_media_required = serializers.SerializerMethodField()

    class Meta:
        model = CustomerSite
        fields = (
            'id', 'customer', 'customer_name', 'label',
            'latitude', 'longitude', 'accuracy', 'landmark',
            'is_default', 'status', 'client_uuid',
            'has_pin', 'media_count', 'media', 'min_media_required',
            'created_by', 'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'status', 'created_by', 'created_at', 'updated_at',
            'has_pin', 'media_count', 'media', 'customer_name',
            'min_media_required',
        )

    def get_min_media_required(self, _obj):
        return MIN_SITE_MEDIA

    def validate(self, attrs):
        instance = getattr(self, 'instance', None)
        status = attrs.get('status')
        # Direct status write is not allowed on serializer create/update —
        # use finalize action. Ignore if somehow passed.
        attrs.pop('status', None)
        if instance and instance.status == CustomerSite.STATUS_FINALIZED:
            # Allow landmark/label tweaks but not clearing pin.
            lat = attrs.get('latitude', instance.latitude)
            lng = attrs.get('longitude', instance.longitude)
            if lat is None or lng is None:
                raise serializers.ValidationError(
                    {'location': 'Cannot clear map pin on a finalized site.'},
                )
        _ = status
        return attrs

    def create(self, validated_data):
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        return CustomerSite.objects.create(created_by=user, **validated_data)


class SiteMediaUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteMedia
        fields = ('id', 'image', 'caption', 'client_uuid')
        read_only_fields = ('id',)

    def validate_image(self, value):
        if value is None:
            raise serializers.ValidationError('Image is required.')
        # Soft size hint — reject absurd uploads (10× client max).
        max_bytes = MAX_SITE_IMAGE_BYTES * 10
        if getattr(value, 'size', 0) > max_bytes:
            raise serializers.ValidationError(
                f'Image exceeds maximum size of {max_bytes} bytes.',
            )
        return value

    def create(self, validated_data):
        site = self.context['site']
        if site.media.count() >= MAX_SITE_MEDIA:
            raise serializers.ValidationError(
                {'media': f'Maximum of {MAX_SITE_MEDIA} photos per site.'},
            )
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        return SiteMedia.objects.create(
            site=site,
            created_by=user,
            **validated_data,
        )


class SiteFinalizeSerializer(serializers.Serializer):
    """Empty body — validates + transitions site to finalized."""

    def save(self, **kwargs):
        site = self.context['site']
        assert_can_finalize(site)
        return finalize_site(site)


class SiteConfigSerializer(serializers.Serializer):
    min_site_media = serializers.IntegerField()
    max_site_media = serializers.IntegerField()
    max_site_image_bytes = serializers.IntegerField()
