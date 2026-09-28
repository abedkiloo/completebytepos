from decimal import Decimal
from pathlib import Path
from django.core.files import File
from products.models import Category, Product
from cms.models import BlogPost
imgs = Path('../../website/assets/images').resolve()
zip_c, _ = Category.objects.get_or_create(name='Zippers & sliders')
stand_c, _ = Category.objects.get_or_create(name='Sofa stands')
web_c, _ = Category.objects.get_or_create(name='Webbing & straps')
items = [
    ('No. 5 nylon zipper (per metre)', 'PV-ZIP5', zip_c, 'african-sofa-craft-detail.jpg', 40, 'Light cushion covers and pillow cases.'),
    ('No. 10 heavy zipper', 'PV-ZIP10', zip_c, None, 0, 'For mattresses and heavy upholstery.'),
    ('Golden trophy sofa stand', 'PV-STD1', stand_c, 'african-sofa-artisan-hero.jpg', 12, 'Decorative 15 cm stand with screw plate.'),
    ('Spiral wooden sofa leg', 'PV-STD2', stand_c, None, 5, 'Hand-turned look for classic sofas.'),
    ('50 mm seat webbing roll', 'PV-WEB50', web_c, 'african-upholstery-team.jpg', 8, 'Elastic webbing for seat suspension.'),
]
for name, sku, cat, img, qty, desc in items:
    p, created = Product.objects.get_or_create(sku=sku, defaults=dict(name=name, category=cat, price=Decimal('150'), stock_quantity=qty, description=desc))
    if created and img:
        with open(imgs / img, 'rb') as f:
            p.image.save(img, File(f), save=True)
posts = [
    ('How to choose the right sofa stand', 'sofa stands, legs', 'african-sofa-artisan-hero.jpg',
     'Picking a stand is about **height, load and style**.\n\n## Measure the height\nMost 3-seaters sit well on 12–15 cm legs.\n\n## Check the load\n- Screw plates spread weight\n- Four legs for small chairs, six for long sofas\n\n> Send us a photo of your frame and we will match a stand.'),
    ('Zipper sizes explained: No. 5 vs No. 10', 'zippers', None,
     'Use **No. 5** for cushions and **No. 10** for mattresses.\n\n## Quick guide\n1. No. 5 — light covers\n2. No. 7/8 — sofa cushions\n3. No. 10 — heavy duty'),
]
for title, tags, img, body in posts:
    post, created = BlogPost.objects.get_or_create(title=title, defaults=dict(body=body, tags=tags, status='published', excerpt=body.split('\n')[0].replace('**','')[:150]))
    if created and img:
        with open(imgs / img, 'rb') as f:
            post.cover_image.save(img, File(f), save=True)
print('seeded', Product.objects.count(), 'products', BlogPost.objects.count(), 'posts')
