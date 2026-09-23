import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import DeliveryRouteMap, { attachGoogleRouteMap, FallbackRouteMap } from './DeliveryRouteMap';

const geometry = {
  source: 'straight',
  depot: { latitude: -1.29, longitude: 36.82, label: 'HQ', placeholder: true },
  path: [
    { latitude: -1.29, longitude: 36.82 },
    { latitude: -1.30, longitude: 36.80 },
  ],
  stops: [
    { id: 4, sequence: 1, label: 'Blue gate', latitude: -1.30, longitude: 36.80 },
  ],
};

describe('DeliveryRouteMap', () => {
  test('fallback map lists shop and numbered stop', () => {
    const onStop = jest.fn();
    render(<FallbackRouteMap geometry={geometry} onStopClick={onStop} />);
    fireEvent.click(screen.getByTestId('delivery-map-stop-4'));
    expect(onStop).toHaveBeenCalledWith(4);
    expect(screen.getByTestId('delivery-map-depot')).toBeInTheDocument();
  });

  test('empty geometry and google attach', async () => {
    render(<DeliveryRouteMap geometry={null} />);
    expect(screen.getByTestId('delivery-route-map-empty')).toBeInTheDocument();

    render(<DeliveryRouteMap geometry={geometry} />);
    expect(screen.getByTestId('delivery-route-map-fallback')).toBeInTheDocument();
    expect(screen.getByText(/straight fallback/i)).toBeInTheDocument();

    const clicks = [];
    const fakeMaps = {
      maps: {
        Map: function Map() {
          this.fitBounds = jest.fn();
        },
        LatLngBounds: function LatLngBounds() {
          this.extend = jest.fn();
        },
        Marker: function Marker(opts) {
          this.position = opts.position;
          this.getPosition = () => opts.position;
          this.addListener = (event, cb) => {
            if (event === 'click' && opts.label !== 'S') cb();
          };
        },
        Polyline: jest.fn(),
      },
    };
    attachGoogleRouteMap(fakeMaps, {}, geometry, (id) => clicks.push(id));
    expect(fakeMaps.maps.Polyline).toHaveBeenCalled();
    expect(clicks).toEqual([4]);

    const loadMaps = jest.fn().mockResolvedValue(fakeMaps);
    const { unmount } = render(
      <DeliveryRouteMap geometry={{ ...geometry, source: 'google', depot: { ...geometry.depot, placeholder: false } }} loadMaps={loadMaps} />,
    );
    unmount();
  });

  test('loadMaps success hides fallback', async () => {
    const original = process.env.REACT_APP_GOOGLE_MAPS_KEY;
    process.env.REACT_APP_GOOGLE_MAPS_KEY = 'AIzaSyWebTest';
    const loadMaps = jest.fn().mockResolvedValue({
      maps: {
        Map: function Map() { this.fitBounds = jest.fn(); },
        LatLngBounds: function LatLngBounds() { this.extend = jest.fn(); },
        Marker: function Marker(opts) {
          this.getPosition = () => opts.position;
        },
        Polyline: jest.fn(),
      },
    });
    render(<DeliveryRouteMap geometry={{ ...geometry, source: 'google' }} loadMaps={loadMaps} />);
    await waitFor(() => expect(loadMaps).toHaveBeenCalled());
    await waitFor(() => expect(screen.queryByTestId('delivery-route-map-fallback')).not.toBeInTheDocument());
    process.env.REACT_APP_GOOGLE_MAPS_KEY = original;
  });

  test('loadMaps failure keeps fallback', async () => {
    const original = process.env.REACT_APP_GOOGLE_MAPS_KEY;
    process.env.REACT_APP_GOOGLE_MAPS_KEY = 'AIzaSyWebTest';
    const loadMaps = jest.fn().mockRejectedValue(new Error('nope'));
    render(<DeliveryRouteMap geometry={geometry} loadMaps={loadMaps} />);
    await waitFor(() => expect(loadMaps).toHaveBeenCalled());
    expect(await screen.findByTestId('delivery-route-map-fallback')).toBeInTheDocument();
    process.env.REACT_APP_GOOGLE_MAPS_KEY = original;
  });

  test('single pin skips polyline and empty fallback still renders', () => {
    const fakeMaps = {
      maps: {
        Map: function Map() { this.fitBounds = jest.fn(); },
        LatLngBounds: function LatLngBounds() { this.extend = jest.fn(); },
        Marker: function Marker(opts) {
          this.getPosition = () => opts.position;
        },
        Polyline: jest.fn(),
      },
    };
    const depotOnly = {
      source: '',
      depot: { latitude: -1.29, longitude: 36.82, label: 'HQ' },
      path: [{ latitude: -1.29, longitude: 36.82 }],
      stops: [],
    };
    const map = attachGoogleRouteMap(fakeMaps, {}, depotOnly);
    expect(fakeMaps.maps.Polyline).not.toHaveBeenCalled();
    expect(map.fitBounds).not.toHaveBeenCalled();
    render(<FallbackRouteMap geometry={{ path: [], stops: [] }} />);
    expect(screen.getByTestId('delivery-route-map-fallback')).toBeInTheDocument();
  });
});
