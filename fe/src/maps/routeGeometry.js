export function geometryFromStops(stops = [], depot = null) {
  const depotPin = depot || { latitude: -1.2921, longitude: 36.8219, label: 'Shop', placeholder: true };
  const listed = (stops || []).map((stop, index) => ({
    id: stop.id,
    sequence: stop.sequence ?? index + 1,
    status: stop.status || 'pending',
    label: stop.label || stop.customer_name || `Stop ${stop.sequence ?? index + 1}`,
    latitude: toCoord(stop.latitude ?? stop.site?.latitude),
    longitude: toCoord(stop.longitude ?? stop.site?.longitude),
  }));
  const path = [
    { latitude: Number(depotPin.latitude), longitude: Number(depotPin.longitude) },
    ...listed.filter((s) => s.latitude != null && s.longitude != null),
  ];
  return {
    route_id: null,
    depot: depotPin,
    encoded_polyline: '',
    source: path.length >= 2 ? 'straight' : '',
    path,
    stops: listed,
  };
}

export function pinsFromGeometry(geometry) {
  const pins = [];
  if (geometry?.depot) {
    pins.push({
      id: 'depot',
      sequence: 0,
      isDepot: true,
      label: geometry.depot.label || 'Shop',
      latitude: Number(geometry.depot.latitude),
      longitude: Number(geometry.depot.longitude),
      placeholder: Boolean(geometry.depot.placeholder),
    });
  }
  (geometry?.stops || []).forEach((stop) => {
    if (stop.latitude == null || stop.longitude == null) return;
    pins.push({
      id: stop.id,
      sequence: stop.sequence,
      isDepot: false,
      label: stop.label,
      latitude: Number(stop.latitude),
      longitude: Number(stop.longitude),
    });
  });
  return pins;
}

function toCoord(value) {
  if (value == null || value === '') return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}
