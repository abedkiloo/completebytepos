import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import AppraisalTemplateForm from './AppraisalTemplateForm';

const policy = {
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
  daily_star_bands: [
    { min: 0, stars: 1, label: '' },
    { min: 10000, stars: 2, label: '' },
    { min: 16000, stars: 3, label: '' },
    { min: 20000, stars: 4, label: 'TARGET MET' },
    { min: 24000, stars: 5, label: 'OVER TARGET' },
  ],
  monthly_bonus_bands: [
    { min: 0, stars: 1, bonus: 0, label: '' },
    { min: 600000, stars: 2, bonus: 0, label: '' },
    { min: 800000, stars: 3, bonus: 0, label: '' },
    { min: 1000000, stars: 4, bonus: 2000, label: 'BASE' },
    { min: 1250000, stars: 4.5, bonus: 6000, label: '' },
    { min: 1500000, stars: 5, bonus: 10000, label: 'MAX' },
  ],
  daily_tip_packs: [],
  role_daily_targets: {
    'Super Admin': 20000,
    Admin: 20000,
    Manager: 35000,
    'Sales Personnel': 20000,
    'Field Sales': 25000,
  },
  role_frameworks: {
    Manager: { daily_target: 35000 },
    'Sales Personnel': { daily_target: 20000 },
    'Field Sales': { daily_target: 25000 },
  },
};

describe('AppraisalTemplateForm', () => {
  it('does not offer a daily target for admin roles', () => {
    render(
      <AppraisalTemplateForm saving={false} onSave={jest.fn()} policy={policy} />
    );

    expect(screen.queryByLabelText('Super Admin')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Admin')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Manager')).toBeInTheDocument();
    expect(screen.getByLabelText('Sales Personnel')).toBeInTheDocument();
    expect(screen.getByTestId('appraisal-rules-preview')).toHaveTextContent(/Daily target/i);
  });

  it('preview scales 4★ daily and bonus mins to the selected role target', () => {
    render(
      <AppraisalTemplateForm saving={false} onSave={jest.fn()} policy={policy} />
    );

    fireEvent.change(screen.getByLabelText('Editing role'), { target: { value: 'Manager' } });
    const preview = screen.getByTestId('appraisal-rules-preview');
    expect(preview).toHaveTextContent(/Daily target/);
    expect(preview).toHaveTextContent('35,000');
    expect(preview).toHaveTextContent(/4★ target/);
    // 4★ bonus threshold scales 1M × 35/20 = 1.75M
    expect(preview).toHaveTextContent(/4★ bonus from/);
    expect(preview).toHaveTextContent('1,750,000');
  });
});
