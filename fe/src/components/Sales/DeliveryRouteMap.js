import React, { useEffect, useMemo, useRef, useState } from 'react';
import { mapsJsKey } from '../../maps/mapsConfig';
import { loadGoogleMapsJs } from '../../maps/googleMapsLoader';
import { pinsFromGeometry } from '../../maps/routeGeometry';

export function attachGoogleRouteMap(googleNs, el, geometry, onStopClick) {
  const maps = googleNs.maps;
  const pins = pinsFromGeometry(geometry);
  const center = pins[0] || { latitude: -1.2921, longitude: 36.8219 };
  const map = new maps.Map(el, {
    center: { lat: center.latitude, lng: center.longitude },
    zoom: 13,
    mapTypeControl: false,
    streetViewControl: false,
  });
  const bounds = new maps.LatLngBounds();
  pins.forEach((pin) => {
    const marker = new maps.Marker({
      map,
      position: { lat: pin.latitude, lng: pin.longitude },
      label: pin.isDepot ? 'S' : String(pin.sequence),
      title: pin.label,
    });
    const pos = marker.getPosition ? marker.getPosition() : marker.position;
    if (bounds.extend) bounds.extend(pos);
    if (!pin.isDepot && onStopClick && marker.addListener) {
      marker.addListener('click', () => onStopClick(pin.id));
    }
  });
  const path = (geometry.path || []).map((point) => ({
    lat: Number(point.latitude),
    lng: Number(point.longitude),
  }));
  if (path.length >= 2) {
    new maps.Polyline({
      map,
      path,
      strokeColor: '#1d4ed8',
      strokeWeight: 4,
    });
  }
  if (pins.length > 1 && typeof map.fitBounds === 'function') {
    map.fitBounds(bounds);
  }
  return map;
}

function project(points, width, height) {
  const lats = points.map((p) => p.latitude);
  const lngs = points.map((p) => p.longitude);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);
  const latSpan = Math.max(maxLat - minLat, 0.01);
  const lngSpan = Math.max(maxLng - minLng, 0.01);
  const pad = 24;
  return points.map((p) => ({
    ...p,
    x: pad + ((p.longitude - minLng) / lngSpan) * (width - pad * 2),
    y: pad + ((maxLat - p.latitude) / latSpan) * (height - pad * 2),
  }));
}

export function FallbackRouteMap({ geometry, onStopClick }) {
  const pins = pinsFromGeometry(geometry);
  const pathPoints = (geometry?.path || []).map((p) => ({
    latitude: Number(p.latitude),
    longitude: Number(p.longitude),
  }));
  const draw = pathPoints.length ? pathPoints : pins;
  const width = 640;
  const height = 240;
  const projected = draw.length ? project(draw, width, height) : [];
  const projectedPins = pins.length ? project(pins, width, height) : [];
  const d = projected.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ');

  return (
    <div data-testid="delivery-route-map-fallback" className="rounded-md border bg-muted/30">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-56" role="img" aria-label="Planned delivery route">
        {d ? (
          <path d={d} fill="none" stroke="#1d4ed8" strokeWidth="4" strokeLinejoin="round" />
        ) : null}
        {projectedPins.map((pin) => (
          <g
            key={pin.id}
            data-testid={pin.isDepot ? 'delivery-map-depot' : `delivery-map-stop-${pin.id}`}
            onClick={() => {
              if (!pin.isDepot && onStopClick) onStopClick(pin.id);
            }}
            style={{ cursor: pin.isDepot ? 'default' : 'pointer' }}
          >
            <circle
              cx={pin.x}
              cy={pin.y}
              r={pin.isDepot ? 11 : 10}
              fill={pin.isDepot ? '#0f766e' : '#1d4ed8'}
            />
            <text x={pin.x} y={pin.y + 4} textAnchor="middle" fontSize="11" fill="#fff">
              {pin.isDepot ? 'S' : pin.sequence}
            </text>
          </g>
        ))}
      </svg>
      <ol className="flex flex-wrap gap-2 px-3 pb-3 text-xs text-muted-foreground">
        {pins.map((pin) => (
          <li key={`legend-${pin.id}`}>
            {pin.isDepot ? 'Shop' : `#${pin.sequence}`} {pin.label}
            {pin.placeholder ? ' (default pin — set branch lat/lng)' : ''}
          </li>
        ))}
      </ol>
    </div>
  );
}

const DeliveryRouteMap = ({
  geometry,
  onStopClick,
  loadMaps = loadGoogleMapsJs,
}) => {
  const hostRef = useRef(null);
  const [useGoogle, setUseGoogle] = useState(false);
  const key = useMemo(() => mapsJsKey(), []);

  useEffect(() => {
    if (!key || !geometry) return undefined;
    let cancelled = false;
    loadMaps(key)
      .then((googleNs) => {
        if (cancelled || !hostRef.current) return;
        attachGoogleRouteMap(googleNs, hostRef.current, geometry, onStopClick);
        setUseGoogle(true);
      })
      .catch(() => {
        if (!cancelled) setUseGoogle(false);
      });
    return () => {
      cancelled = true;
    };
  }, [key, geometry, loadMaps, onStopClick]);

  if (!geometry) {
    return (
      <p className="text-sm text-muted-foreground" data-testid="delivery-route-map-empty">
        No planned route yet.
      </p>
    );
  }

  return (
    <div data-testid="delivery-route-map">
      {key ? <div ref={hostRef} className="h-56 w-full rounded-md border" /> : null}
      {useGoogle ? null : <FallbackRouteMap geometry={geometry} onStopClick={onStopClick} />}
      {geometry.source === 'straight' ? (
        <p className="mt-1 text-xs text-muted-foreground">
          Road line is a straight fallback until the Routes API server key is set.
        </p>
      ) : null}
      {geometry.depot?.placeholder ? (
        <p className="text-xs text-muted-foreground">
          Shop pin is a Nairobi default. Save latitude/longitude on the branch to set the depot.
        </p>
      ) : null}
    </div>
  );
};

export default DeliveryRouteMap;
