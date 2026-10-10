import React, { useMemo } from 'react';

import SearchableSelect from '../Shared/SearchableSelect';
import { Label } from '../ui/label';
import {
  kenyaSubCounties,
  kenyaWards,
  useKenyaAdminUnits,
} from '../../hooks/useKenyaAdminUnits';

function FieldWrap({ label, htmlFor, error, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {error ? <p className="text-xs text-destructive">{error}</p> : null}
    </div>
  );
}

export default function KenyaLocationFields({ formData, formErrors, onChange }) {
  const { counties, loading } = useKenyaAdminUnits();

  const toOptions = (names) =>
    names.map((name) => ({ value: name, label: name }));

  const countyOptions = useMemo(
    () => toOptions(Object.keys(counties).sort((a, b) => a.localeCompare(b))),
    [counties]
  );

  const subCountyOptions = useMemo(
    () => toOptions(kenyaSubCounties(counties, formData.county)),
    [counties, formData.county]
  );

  const wardOptions = useMemo(
    () => toOptions(kenyaWards(counties, formData.county, formData.sub_county)),
    [counties, formData.county, formData.sub_county]
  );

  const handleCountyChange = (event) => {
    const value = event.target.value || '';
    onChange('county', value);
    const subs = kenyaSubCounties(counties, value);
    const firstSub = subs[0] || '';
    onChange('sub_county', firstSub);
    const wards = kenyaWards(counties, value, firstSub);
    onChange('ward', wards[0] || '');
  };

  const handleSubCountyChange = (event) => {
    const value = event.target.value || '';
    onChange('sub_county', value);
    const wards = kenyaWards(counties, formData.county, value);
    onChange('ward', wards[0] || '');
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
          disabled={loading || !formData.county}
          invalid={Boolean(formErrors.sub_county)}
        />
      </FieldWrap>
      <FieldWrap label="Ward" htmlFor="cust-ward" error={formErrors.ward}>
        <SearchableSelect
          name="cust-ward"
          value={formData.ward || ''}
          onChange={(event) => onChange('ward', event.target.value || '')}
          options={wardOptions}
          placeholder="Select ward"
          disabled={loading || !formData.sub_county}
          invalid={Boolean(formErrors.ward)}
        />
      </FieldWrap>
      <p className="text-xs text-muted-foreground">Country: Kenya</p>
    </div>
  );
}
