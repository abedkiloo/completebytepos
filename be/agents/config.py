"""Site visit config — documented defaults for mobile + API validation."""

# Minimum SiteMedia rows required before a CustomerSite may finalize.
MIN_SITE_MEDIA = 1

# Soft guidance for clients (enforced client-side; server checks count only).
MAX_SITE_MEDIA = 10

# Suggested max compressed image size for clients (bytes).
MAX_SITE_IMAGE_BYTES = 2 * 1024 * 1024
