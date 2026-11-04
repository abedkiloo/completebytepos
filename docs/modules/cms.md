# cms

## Purpose

Marketing-site blog + enquiry intake; admin CMS vs public website APIs.

## Key models

| Model | Role |
|-------|------|
| `BlogPost` | Published/draft posts |
| `WebsiteEnquiry` | Public enquiry intake |

## Public APIs

Prefix: `/api/cms/` + `/api/public/website/`

## Bounds & invariants

- Public blog only `published` with `published_at` ≤ now.
- Public enquiry is create-only; admin manages posts/enquiries.

## Audit

Admin mutations use audited mixin (`module=cms`).

## Gaps

- Google-style docstrings on models and ``PublicEnquirySerializer`` create path.
- Admin blog ViewSet/serializer methods remain lightly documented; public read serializers inherit base fields only.
