import React from 'react';
import { render, screen } from '@testing-library/react';
import AppraisalProgressCard from './AppraisalProgressCard';

jest.mock('react-router-dom', () => ({
  Link: ({ children, to }) => <a href={to}>{children}</a>,
  MemoryRouter: ({ children }) => <>{children}</>,
}));

const snapshot = {
  staff: { name: 'Ann Cash' },
  greeting: {
    headline: '3-Star day — KES 1,500 to hit the daily target',
    detail: 'Close the gap with conversations. Five moves for today are below.',
  },
  today: {
    date: '2026-09-29',
    sales: 18500,
    stars: 3,
    tone: 'amber',
    target: 20000,
    target_progress: 0.925,
    amount_to_target: 1500,
    label: '',
  },
  month: {
    official_average: 3,
    four_star_month: false,
    progress_to_four_star: 0.29,
    bonus: 2000,
    tone: 'rose',
  },
  year: {
    four_star_months: 1,
    four_star_months_required: 8,
    qualifies: false,
    new_basic: 15000,
    progress_to_increment: 0.125,
    tone: 'rose',
  },
  today_tips: {
    title: 'Help them choose the right sofa stand',
    why: 'Makers buy from the person who stops a wobbly sofa.',
    tips: [
      'Measure with them.',
      'Load first, style second.',
      'Sell a set of four.',
      'Match the floor.',
      'Post a short how-to, not only a product picture.',
    ],
  },
};

describe('AppraisalProgressCard', () => {
  it('shows daily target progress and five sales tips, not bonus', () => {
    render(<AppraisalProgressCard snapshot={snapshot} />);

    expect(screen.getByText(/of KES 20,000 daily target/)).toBeInTheDocument();
    expect(screen.getByText(/toward a 4-star month/)).toBeInTheDocument();
    expect(screen.getByTestId('appraisal-daily-tips')).toBeInTheDocument();
    expect(screen.getByText('Help them choose the right sofa stand')).toBeInTheDocument();
    expect(screen.getByText('Post a short how-to, not only a product picture.')).toBeInTheDocument();
    expect(screen.queryByText(/bonus/i)).not.toBeInTheDocument();
    expect(screen.getByText(/Still needed today/)).toBeInTheDocument();
  });

  it('shows one today move on the compact home card', () => {
    render(<AppraisalProgressCard snapshot={snapshot} compact />);

    expect(screen.getByTestId('appraisal-today-move')).toHaveTextContent('Today’s move');
    expect(screen.getByTestId('appraisal-today-move')).toHaveTextContent('Measure with them.');
    expect(screen.queryByTestId('appraisal-daily-tips')).not.toBeInTheDocument();
  });
});
