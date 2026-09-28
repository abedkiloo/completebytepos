"""Public website content (blog) served to the marketing site."""

from __future__ import annotations

import math
import re

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

WORDS_PER_MINUTE = 200


class BlogPostQuerySet(models.QuerySet):
    def published(self):
        return self.filter(
            status=BlogPost.STATUS_PUBLISHED,
            published_at__isnull=False,
            published_at__lte=timezone.now(),
        )


class BlogPost(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_PUBLISHED, 'Published'),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    excerpt = models.CharField(
        max_length=300,
        blank=True,
        help_text='Short summary shown on the blog list and in search results.',
    )
    body = models.TextField(
        help_text='Markdown: ## headings, **bold**, *italic*, [links](https://…), - lists.',
    )
    cover_image = models.ImageField(upload_to='blog/', blank=True, null=True)
    cover_image_alt = models.CharField(max_length=200, blank=True)
    tags = models.CharField(
        max_length=200,
        blank=True,
        help_text='Comma-separated, e.g. "zippers, sofa stands".',
    )
    meta_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True,
    )
    is_featured = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='blog_posts',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = BlogPostQuerySet.as_manager()

    class Meta:
        ordering = ['-published_at', '-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        if self.status == self.STATUS_PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def _unique_slug(self) -> str:
        base = slugify(self.title)[:200] or 'post'
        slug = base
        n = 2
        while BlogPost.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug = f'{base}-{n}'
            n += 1
        return slug

    @property
    def tag_list(self) -> list[str]:
        return [t.strip() for t in self.tags.split(',') if t.strip()]

    @property
    def reading_minutes(self) -> int:
        words = len(re.findall(r'\w+', self.body or ''))
        return max(1, math.ceil(words / WORDS_PER_MINUTE))

    @property
    def summary(self) -> str:
        if self.excerpt:
            return self.excerpt
        plain = re.sub(r'[#*_>\[\]()`-]', '', self.body or '')
        plain = ' '.join(plain.split())
        return plain[:157] + '…' if len(plain) > 160 else plain
