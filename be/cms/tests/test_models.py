from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from cms.models import BlogPost


class BlogPostModelTest(TestCase):
    def test_slug_generated_from_title_and_kept_unique(self):
        a = BlogPost.objects.create(title='Zipper sizes explained', body='x')
        b = BlogPost.objects.create(title='Zipper sizes explained', body='y')
        self.assertEqual(a.slug, 'zipper-sizes-explained')
        self.assertEqual(b.slug, 'zipper-sizes-explained-2')

    def test_explicit_slug_is_kept(self):
        post = BlogPost.objects.create(title='Anything', slug='custom-url', body='x')
        self.assertEqual(post.slug, 'custom-url')

    def test_publishing_stamps_published_at_once(self):
        post = BlogPost.objects.create(title='Draft', body='x')
        self.assertIsNone(post.published_at)
        post.status = BlogPost.STATUS_PUBLISHED
        post.save()
        first = post.published_at
        self.assertIsNotNone(first)
        post.title = 'Edited'
        post.save()
        self.assertEqual(post.published_at, first)

    def test_published_queryset_excludes_drafts_and_future_posts(self):
        live = BlogPost.objects.create(
            title='Live', body='x', status=BlogPost.STATUS_PUBLISHED,
        )
        BlogPost.objects.create(title='Draft', body='x')
        BlogPost.objects.create(
            title='Scheduled', body='x', status=BlogPost.STATUS_PUBLISHED,
            published_at=timezone.now() + timedelta(days=2),
        )
        self.assertEqual(list(BlogPost.objects.published()), [live])

    def test_tag_list_reading_minutes_and_summary(self):
        post = BlogPost(
            title='T',
            tags=' zippers, ,sofa stands ',
            body='## Heading\n' + ('word ' * 450),
        )
        self.assertEqual(post.tag_list, ['zippers', 'sofa stands'])
        self.assertEqual(post.reading_minutes, 3)
        self.assertTrue(post.summary.endswith('…'))
        self.assertLessEqual(len(post.summary), 160)
        self.assertNotIn('#', post.summary)

    def test_excerpt_wins_over_generated_summary(self):
        post = BlogPost(title='T', excerpt='Short intro', body='Long body text')
        self.assertEqual(post.summary, 'Short intro')
