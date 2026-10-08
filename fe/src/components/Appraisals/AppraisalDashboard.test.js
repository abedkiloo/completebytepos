import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AppraisalDashboard from './AppraisalDashboard';

jest.mock('react-router-dom', () => ({
  Link: ({ children, to, ...props }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
  MemoryRouter: ({ children }) => <>{children}</>,
}));

jest.mock('recharts', () => ({
  ResponsiveContainer: ({ children }) => <div data-testid="chart">{children}</div>,
  LineChart: ({ children }) => <div>{children}</div>,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  CartesianGrid: () => null,
}));

const snapshot = {
  has_personal_target: true,
  greeting: {
    headline: '3-Star day — KES 1,500 to hit the daily target',
    detail: 'Close the gap with conversations.',
  },
  today: {
    date: '2026-10-03',
    sales: 18500,
    stars: 3,
    tone: 'amber',
    target: 20000,
    target_progress: 0.925,
    amount_to_target: 1500,
    amount_to_next: 1500,
    status_label: 'Near target',
    label: '',
  },
  month: {
    sales: 420000,
    expected_sales: 520000,
    official_average: 4.12,
    four_star_month: true,
    four_star_days: 10,
    days_elapsed: 15,
    working_days: 26,
    days_remaining: 11,
    bonus: 4000,
    next_bonus: 7000,
    amount_to_next_bonus: 125000,
    tone: 'emerald',
    days: [
      { date: '2026-10-01', sales: 21000, stars: 4, tone: 'emerald' },
      { date: '2026-10-02', sales: 18000, stars: 3, tone: 'amber' },
      { date: '2026-10-03', sales: 18500, stars: 3, tone: 'amber' },
    ],
  },
  year: {
    basic_pay: 15000,
    four_star_months: 7,
    four_star_months_required: 8,
    ytd_average: 4.12,
    increment_message: 'One more 4-Star month to qualify for your KES 3,000 annual increment.',
    progress_to_increment: 0.875,
    months: [],
  },
  policy: {
    show_year_end_increment: false,
    year_end_increment: 3000,
    annual_avg_required: 4,
    four_star_month_min_avg: 4,
    monthly_bonus_bands: [
      { min: 0, stars: 1, bonus: 0 },
      { min: 800000, stars: 3, bonus: 0 },
      { min: 1000000, stars: 4, bonus: 2000 },
    ],
  },
  // Role-scoped rules must win over global policy for ladders and salary hints.
  applied_policy: {
    role: 'Manager',
    show_year_end_increment: true,
    year_end_increment: 5000,
    annual_avg_required: 4,
    four_star_month_min_avg: 4,
    bonus_min_stars: 4,
    monthly_bonus_bands: [
      { min: 0, stars: 1, bonus: 0 },
      { min: 1400000, stars: 3, bonus: 0 },
      { min: 1750000, stars: 4, bonus: 4000 },
      { min: 2187500, stars: 5, bonus: 7000 },
    ],
  },
  today_tips: {
    title: 'Follow up',
    why: 'It works',
    tips: ['Call five customers you already sold to.'],
  },
};

describe('AppraisalDashboard', () => {
  it('shows today, remaining amount, bonus ladder, and salary growth', () => {
    render(<AppraisalDashboard snapshot={snapshot} />);

    expect(screen.getByTestId('appraisal-today')).toHaveTextContent('KES 18,500');
    expect(screen.getByTestId('appraisal-remaining')).toHaveTextContent(/1,500 more to reach 4 Stars/);
    expect(screen.getByTestId('appraisal-month')).toHaveTextContent(/4.12/);
    expect(screen.getByTestId('appraisal-bonus')).toHaveTextContent(/KES 4,000/);
    expect(screen.getByTestId('appraisal-bonus')).toHaveTextContent(/125,000 more to unlock/);
    // Applied Manager ladder (1.75M), not global Sales ladder (1M).
    expect(screen.getByTestId('appraisal-bonus')).toHaveTextContent(/1,750,000/);
    expect(screen.getByTestId('appraisal-salary')).toHaveTextContent(/One more 4-Star month/);
    expect(screen.getByTestId('appraisal-calendar')).toHaveTextContent(/MON|TUE|WED|THU|FRI|SAT|SUN/);
    expect(screen.queryByRole('link', { name: /Open sales for/ })).not.toBeInTheDocument();
  });

  it('links each day tile to that day’s sales when dayHref is given', () => {
    render(
      <MemoryRouter>
        <AppraisalDashboard snapshot={snapshot} dayHref={(d) => `/sales/daily?date=${d}`} />
      </MemoryRouter>
    );
    expect(screen.getByRole('link', { name: 'Open sales for 2026-10-02' })).toHaveAttribute(
      'href',
      '/sales/daily?date=2026-10-02'
    );
  });
});
