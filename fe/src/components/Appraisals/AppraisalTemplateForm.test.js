import React from 'react';
import { render, screen } from '@testing-library/react';
import AppraisalTemplateForm from './AppraisalTemplateForm';

describe('AppraisalTemplateForm', () => {
  it('does not offer a daily target for admin roles', () => {
    render(
      <AppraisalTemplateForm
        saving={false}
        onSave={jest.fn()}
        policy={{
          basic_pay: 15000,
          daily_target: 20000,
          manager_daily_target: 35000,
          year_end_increment: 3000,
          working_days: 26,
          four_star_month_min_avg: 4,
          four_star_months_required: 8,
          annual_avg_required: 4,
          show_year_end_increment: false,
          greet_when_no_sticky_notes: true,
          show_on_home: true,
          daily_star_bands: [{ min: 0, stars: 1, label: '' }],
          monthly_bonus_bands: [{ min: 0, stars: 1, bonus: 0, label: '' }],
          daily_tip_packs: [],
          role_daily_targets: {
            'Super Admin': 20000,
            Admin: 20000,
            Manager: 35000,
            'Sales Personnel': 20000,
            'Field Sales': 20000,
          },
        }}
      />
    );

    expect(screen.queryByLabelText('Super Admin')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Admin')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Manager')).toBeInTheDocument();
    expect(screen.getByLabelText('Sales Personnel')).toBeInTheDocument();
    expect(screen.getByTestId('appraisal-rules-preview')).toHaveTextContent(/Daily target/i);
  });
});
