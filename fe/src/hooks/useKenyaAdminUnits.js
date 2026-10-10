import { useEffect, useState } from 'react';

import { customersAPI } from '../services/api';

const FALLBACK_DEFAULTS = {
  county: 'Nairobi',
  sub_county: 'Starehe',
  ward: 'Landimawe',
};

let cachedPayload = null;
let inflight = null;

async function loadKenyaAdminUnits() {
  if (cachedPayload) return cachedPayload;
  if (inflight) return inflight;
  inflight = customersAPI
    .kenyaLocations()
    .then((response) => {
      cachedPayload = response.data;
      return cachedPayload;
    })
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

export function useKenyaAdminUnits() {
  const [payload, setPayload] = useState(cachedPayload);
  const [loading, setLoading] = useState(!cachedPayload);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    loadKenyaAdminUnits()
      .then((data) => {
        if (active) {
          setPayload(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (active) {
          setError(err);
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const counties = payload?.counties ?? {};
  const defaults = payload?.defaults ?? FALLBACK_DEFAULTS;

  return { counties, defaults, loading, error };
}

export function kenyaSubCounties(counties, county) {
  if (!county || !counties[county]) return [];
  return Object.keys(counties[county]).sort((a, b) => a.localeCompare(b));
}

export function kenyaWards(counties, county, subCounty) {
  if (!county || !subCounty || !counties[county]?.[subCounty]) return [];
  return [...counties[county][subCounty]].sort((a, b) => a.localeCompare(b));
}
