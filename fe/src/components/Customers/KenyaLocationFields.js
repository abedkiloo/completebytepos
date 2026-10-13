import React, { useEffect, useMemo } from 'react';

import SearchableSelect from '../Shared/SearchableSelect';
import { Label } from '../ui/label';
import {
  kenyaSubCounties,
  kenyaWards,
  useKenyaAdminUnits,
} from '../../hooks/useKenyaAdminUnits';

function FieldWrap({ label, htmlFor, error, hint, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {error ? (
        <p className="text-xs text-destructive">{error}</p>
      ) : hint ? (
        <p className="text-xs text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}

/**
 * County → sub-county → ward cascading selects + optional location name.
 * Matches mobile `KenyaLocationFields` + Location name field.
 *
 * `onChange` accepts either `(field, value)` or a patch object
 * `{ county, sub_county, ward, city?, address? }` so cascades apply atomically.
 */
export default function KenyaLocationFields({
  formData,
  formErrors = {},
  onChange,
  showLocationName = true,
}) {
  const { counties, defaults, loading } = useKenyaAdminUnits();

  const toOptions = (names) =>
    names.map((name) => ({ value: name, label: name }));

  const countyNames = useMemo(
    () => Object.keys(counties).sort((a, b) => a.localeCompare(b)),
    [counties]
  );

  const countyOptions = useMemo(() => toOptions(countyNames), [countyNames]);

  const subCountyNames = useMemo(
    () => kenyaSubCounties(counties, formData.county),
    [counties, formData.county]
  );

  const subCountyOptions = useMemo(() => toOptions(subCountyNames), [subCountyNames]);

  const wardNames = useMemo(
    () => kenyaWards(counties, formData.county, formData.sub_county),
    [counties, formData.county, formData.sub_county]
  );

  const wardOptions = useMemo(() => toOptions(wardNames), [wardNames]);

  // When units load, coerce invalid selections to defaults / first option (same as app).
  useEffect(() => {
    if (loading || countyNames.length === 0) return;

    const county = countyNames.includes(formData.county)
      ? formData.county
      : defaults.county && countyNames.includes(defaults.county)
        ? defaults.county
        : countyNames[0];

    const subs = kenyaSubCounties(counties, county);
    const subCounty = subs.includes(formData.sub_county)
      ? formData.sub_county
      : defaults.sub_county && subs.includes(defaults.sub_county)
        ? defaults.sub_county
        : subs[0] || '';

    const wards = kenyaWards(counties, county, subCounty);
    const ward = wards.includes(formData.ward)
      ? formData.ward
      : defaults.ward && wards.includes(defaults.ward)
        ? defaults.ward
        : wards[0] || '';

    if (
      county !== formData.county ||
      subCounty !== formData.sub_county ||
      ward !== formData.ward
    ) {
      onChange({
        county,
        sub_county: subCounty,
        ward,
        city: county,
      });
    }
    // Only re-run when catalog loads or current selection becomes invalid.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, counties, countyNames.join('|')]);

  const handleCountyChange = (event) => {
    const value = event.target.value || '';
    const subs = kenyaSubCounties(counties, value);
    const firstSub = subs[0] || '';
    const wards = kenyaWards(counties, value, firstSub);
    onChange({
      county: value,
      sub_county: firstSub,
      ward: wards[0] || '',
      city: value,
    });
  };

  const handleSubCountyChange = (event) => {
    const value = event.target.value || '';
    const wards = kenyaWards(counties, formData.county, value);
    onChange({
      sub_county: value,
      ward: wards[0] || '',
    });
  };

  const handleWardChange = (event) => {
    onChange('ward', event.target.value || '');
  };

  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Location <span className="font-normal normal-case">(Kenya)</span>
      </p>
      <FieldWrap label="County" htmlFor="cust-county" error={formErrors.county}>
        <SearchableSelect
          name="cust-county"
          value={formData.county || ''}
          onChange={handleCountyChange}
          options={countyOptions}
          placeholder={loading ? 'Loading counties…' : 'Select county'}
          disabled={loading || countyOptions.length === 0}
          invalid={Boolean(formErrors.county)}
        />
      </FieldWrap>
      <FieldWrap label="Sub-county" htmlFor="cust-sub-county" error={formErrors.sub_county}>
        <SearchableSelect
          name="cust-sub-county"
          value={formData.sub_county || ''}
          onChange={handleSubCountyChange}
          options={subCountyOptions}
          placeholder="Select sub-county"
          disabled={loading || !formData.county || subCountyOptions.length === 0}
          invalid={Boolean(formErrors.sub_county)}
        />
      </FieldWrap>
      <FieldWrap label="Ward" htmlFor="cust-ward" error={formErrors.ward}>
        <SearchableSelect
          name="cust-ward"
          value={formData.ward || ''}
          onChange={handleWardChange}
          options={wardOptions}
          placeholder="Select ward"
          disabled={loading || !formData.sub_county || wardOptions.length === 0}
          invalid={Boolean(formErrors.ward)}
        />
      </FieldWrap>
      <p className="text-xs text-muted-foreground">Country: Kenya</p>

      {showLocationName ? (
        <FieldWrap
          label="Location name"
          htmlFor="cust-address"
          error={formErrors.address}
          hint="Optional. Estate, market, or area. County / sub-county / ward selection stays above."
        >
          <textarea
            id="cust-address"
            name="cust-address"
            value={formData.address || ''}
            onChange={(e) => onChange('address', e.target.value)}
            rows={2}
            className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
            placeholder="e.g. Gikomba, Pipeline, opposite the bus stage…"
          />
        </FieldWrap>
      ) : null}
    </div>
  );
}
