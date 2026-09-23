"""Google encoded polyline (same format as Routes API)."""


def encode_polyline(points) -> str:
    """Encode [(lat, lng), ...] using the Google encoded polyline algorithm."""
    result = []
    prev_lat = 0
    prev_lng = 0
    for lat, lng in points:
        lat_e5 = int(round(float(lat) * 1e5))
        lng_e5 = int(round(float(lng) * 1e5))
        result.append(_encode_signed(lat_e5 - prev_lat))
        result.append(_encode_signed(lng_e5 - prev_lng))
        prev_lat = lat_e5
        prev_lng = lng_e5
    return ''.join(result)


def decode_polyline(encoded: str) -> list[tuple[float, float]]:
    """Decode a Google encoded polyline to [(lat, lng), ...]."""
    if not encoded:
        return []
    points = []
    index = 0
    lat = 0
    lng = 0
    length = len(encoded)
    while index < length:
        lat_change, index = _decode_signed(encoded, index)
        lng_change, index = _decode_signed(encoded, index)
        lat += lat_change
        lng += lng_change
        points.append((lat / 1e5, lng / 1e5))
    return points


def _encode_signed(value: int) -> str:
    value = ~(value << 1) if value < 0 else (value << 1)
    chunks = []
    while value >= 0x20:
        chunks.append(chr((0x20 | (value & 0x1F)) + 63))
        value >>= 5
    chunks.append(chr(value + 63))
    return ''.join(chunks)


def _decode_signed(encoded: str, index: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        if index >= len(encoded):
            break
        byte = ord(encoded[index]) - 63
        index += 1
        result |= (byte & 0x1F) << shift
        shift += 5
        if byte < 0x20:
            break
    value = ~(result >> 1) if result & 1 else (result >> 1)
    return value, index
