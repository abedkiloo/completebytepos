"""
CMS and public website serializers.

Public entry points:
    - ``PublicBlogPostListSerializer`` / ``PublicBlogPostDetailSerializer`` — read-only blog
    - ``PublicEnquirySerializer`` — anonymous enquiry create
    - ``BlogPostAdminSerializer`` — staff blog CRUD
"""

from __future__ import annotations

from django.conf import settings
from rest_framework import serializers

from config.media_urls import absolute_media_url
from products.models import Category, Product

from .models import BlogPost, WebsiteEnquiry


def _image_url(serializer, field):
    if not field:
        return None
    try:
        return absolute_media_url(serializer.context.get('request'), field.url)
    except ValueError:
        return None


class _BlogPostPublicBase(serializers.ModelSerializer):
    cover_image_url = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    excerpt = serializers.CharField(source='summary', read_only=True)
    author_name = serializers.SerializerMethodField()
    reading_minutes = serializers.IntegerField(read_only=True)

    def get_cover_image_url(self, obj):
        return _image_url(self, obj.cover_image)

    def get_tags(self, obj):
        return obj.tag_list

    def get_author_name(self, obj):
        if not obj.author:
            return 'Omuwenga Suppliers'
        return obj.author.get_full_name() or 'Omuwenga Suppliers'


class PublicBlogPostListSerializer(_BlogPostPublicBase):
    class Meta:
        model = BlogPost
        fields = [
            'slug', 'title', 'excerpt', 'cover_image_url', 'cover_image_alt',
            'tags', 'is_featured', 'published_at', 'updated_at',
            'reading_minutes', 'author_name',
        ]


class PublicBlogPostDetailSerializer(_BlogPostPublicBase):
    meta_title = serializers.SerializerMethodField()
    meta_description = serializers.SerializerMethodField()

    class Meta:
        model = BlogPost
        fields = PublicBlogPostListSerializer.Meta.fields + [
            'body', 'meta_title', 'meta_description',
        ]

    def get_meta_title(self, obj):
        return obj.meta_title or obj.title

    def get_meta_description(self, obj):
        return obj.meta_description or obj.summary


class BlogPostAdminSerializer(serializers.ModelSerializer):
    cover_image_url = serializers.SerializerMethodField()
    author_name = serializers.SerializerMethodField()
    remove_cover_image = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = BlogPost
        fields = [
            'id', 'title', 'slug', 'excerpt', 'body', 'cover_image',
            'cover_image_url', 'cover_image_alt', 'remove_cover_image', 'tags',
            'meta_title', 'meta_description', 'status', 'is_featured',
            'published_at', 'author', 'author_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['author', 'created_at', 'updated_at']
        extra_kwargs = {
            'slug': {'required': False, 'allow_blank': True},
            'cover_image': {'write_only': True, 'required': False},
        }

    def get_cover_image_url(self, obj):
        return _image_url(self, obj.cover_image)

    def get_author_name(self, obj):
        if not obj.author:
            return ''
        return obj.author.get_full_name() or obj.author.username

    def validate_title(self, value):
        value = (value or '').strip()
        if not value:
            raise serializers.ValidationError('Title is required.')
        return value

    def validate_body(self, value):
        if not (value or '').strip():
            raise serializers.ValidationError('Write the post content before saving.')
        return value

    def validate_slug(self, value):
        value = (value or '').strip()
        if not value:
            return ''
        qs = BlogPost.objects.filter(slug=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Another post already uses this URL.')
        return value

    def _apply_cover_removal(self, instance, remove):
        if remove and instance.cover_image:
            instance.cover_image.delete(save=False)
            instance.cover_image = None

    def create(self, validated_data):
        validated_data.pop('remove_cover_image', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        remove = validated_data.pop('remove_cover_image', False)
        if not validated_data.get('slug', instance.slug):
            validated_data.pop('slug')
        if remove and 'cover_image' not in validated_data:
            self._apply_cover_removal(instance, True)
        if validated_data.get('status') == BlogPost.STATUS_DRAFT:
            validated_data.setdefault('published_at', None)
        return super().update(instance, validated_data)


class PublicCategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(source='public_product_count', read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'parent', 'product_count']


class PublicProductSerializer(serializers.ModelSerializer):
    """Safe, public subset of a product — never cost, stock counts or suppliers."""

    category = serializers.SerializerMethodField()
    subcategory = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    in_stock = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'sku', 'category', 'subcategory', 'description',
            'image_url', 'unit', 'has_variants', 'in_stock',
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if getattr(settings, 'WEBSITE_SHOW_PRICES', False):
            data['price'] = str(instance.price)
        return data

    def get_category(self, obj):
        if not obj.category_id:
            return None
        return {'id': obj.category_id, 'name': obj.category.name}

    def get_subcategory(self, obj):
        if not obj.subcategory_id:
            return None
        return {'id': obj.subcategory_id, 'name': obj.subcategory.name}

    def get_image_url(self, obj):
        return _image_url(self, obj.image)

    def get_in_stock(self, obj):
        if not obj.track_stock:
            return True
        return obj.stock_quantity > 0


class PublicEnquirySerializer(serializers.ModelSerializer):
    """
    Validate and create a public website enquiry (unauthenticated).

    Requires name (≥ 2 chars), phone (9–15 digits), and either ``message`` or
    ``interest``. ``product_id`` links an active product when provided.

    Side effects:
        Inserts ``WebsiteEnquiry`` with ``status=new``; no SMS or audit in serializer.
    """

    product_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = WebsiteEnquiry
        fields = [
            'id', 'name', 'phone', 'business', 'location', 'interest',
            'message', 'product_id', 'status',
        ]
        read_only_fields = ['id', 'status']

    def validate_name(self, value):
        value = (value or '').strip()
        if len(value) < 2:
            raise serializers.ValidationError('Enter your name.')
        return value

    def validate_phone(self, value):
        raw = (value or '').strip()
        digits = ''.join(ch for ch in raw if ch.isdigit())
        if len(digits) < 9 or len(digits) > 15:
            raise serializers.ValidationError('Enter a phone number we can call.')
        return raw

    def validate(self, attrs):
        if not (attrs.get('message') or '').strip() and not (attrs.get('interest') or '').strip():
            raise serializers.ValidationError('Tell us which fitting you need.')
        return attrs

    def create(self, validated_data):
        """
        Persist enquiry after stripping optional product and text fields.

        Args:
            validated_data: Validated serializer fields including write-only ``product_id``.

        Returns:
            New ``WebsiteEnquiry`` instance (``status=new``).

        Side effects:
            Single INSERT; inactive/missing ``product_id`` stores null product FK.
        """
        product_id = validated_data.pop('product_id', None)
        if product_id:
            validated_data['product'] = Product.objects.filter(pk=product_id, is_active=True).first()
        for key in ('business', 'location', 'interest', 'message'):
            if key in validated_data and isinstance(validated_data[key], str):
                validated_data[key] = validated_data[key].strip()
        return WebsiteEnquiry.objects.create(**validated_data)


class WebsiteEnquiryAdminSerializer(serializers.ModelSerializer):
    product_name = serializers.SerializerMethodField()

    class Meta:
        model = WebsiteEnquiry
        fields = [
            'id', 'name', 'phone', 'business', 'location', 'interest',
            'message', 'product', 'product_name', 'status', 'created_at',
        ]
        read_only_fields = [
            'id', 'name', 'phone', 'business', 'location', 'interest',
            'message', 'product', 'product_name', 'created_at',
        ]

    def get_product_name(self, obj):
        return obj.product.name if obj.product_id else ''
