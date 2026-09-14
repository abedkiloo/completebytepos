"""Delivery run configuration (S09)."""

# Complete requires ProofOfDelivery when True.
REQUIRE_POD_TO_COMPLETE = True

# Offline policy: clients MAY enqueue POD capture to the outbox when offline.
# Server accepts the same POD payload when connectivity returns (idempotent by stop).
ALLOW_OFFLINE_POD_QUEUE = True
