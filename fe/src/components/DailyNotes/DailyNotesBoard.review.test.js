import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

import DailyNotesBoard from './DailyNotesBoard';

const note = {
  id: 4,
  title: 'Close the till',
  content: 'Counted and locked.',
  is_done: true,
  author: 1,
  author_id: 1,
  reviews: [
    { id: 9, reviewer_id: 2, reviewer_name: 'Rita', status: 'pending', comment: '' },
  ],
};

describe('DailyNotesBoard review', () => {
  it('shows a waiting review and lets that person mark it reviewed', () => {
    const onCompleteReview = jest.fn();
    render(
      <DailyNotesBoard
        notes={[note]}
        currentUserId={2}
        viewAll={false}
        onToggle={jest.fn()}
        onMove={jest.fn()}
        onEdit={jest.fn()}
        onDelete={jest.fn()}
        canModifyEntry={() => false}
        reviewers={[{ id: 3, display_name: 'Sam' }]}
        onCompleteReview={onCompleteReview}
      />
    );

    expect(screen.getByTestId('note-review-waiting-4')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('daily-note-expand-4'));
    fireEvent.change(screen.getByTestId('note-review-comment-4'), {
      target: { value: 'Looks correct' },
    });
    fireEvent.click(screen.getByTestId('note-review-finish-4'));
    expect(onCompleteReview).toHaveBeenCalledWith(note, 9, 'Looks correct');
    expect(screen.queryByText('0711777001')).not.toBeInTheDocument();
  });
});
