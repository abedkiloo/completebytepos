"""Site visit / delivery-location config for mobile + API validation."""

# Photos are optional for visit-orders (pin + customer are required).
MIN_SITE_MEDIA = 0

# Soft guidance for clients when photos are attached.
MAX_SITE_MEDIA = 10

# Suggested max compressed image size for clients (bytes).
# Client hint for site media; server still compresses to ≤ 1.5 MiB.
MAX_SITE_IMAGE_BYTES = int(1.5 * 1024 * 1024)
