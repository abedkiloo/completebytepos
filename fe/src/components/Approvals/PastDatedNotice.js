import React from 'react';
import { CalendarClock } from 'lucide-react';
import { formatDate } from '../../utils/formatters';
import { earliestBusinessDay, PAST_DATED_ADMIN_ONLY_MESSAGE } from '../../utils/pastDatedApproval';

export default function PastDatedNotice({ dates, blocked }) {
  const day = earliestBusinessDay(...(dates || []));
  return (
    <div
      className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-950 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-100"
      data-testid="past-dated-notice"
    >
      <CalendarClock className="mt-0.5 h-4 w-4 shrink-0" />
      <p>
        {day ? `Dated ${formatDate(`${day}T12:00:00`)}. ` : ''}
        {blocked
          ? PAST_DATED_ADMIN_ONLY_MESSAGE
          : 'Past-dated item — admin approval.'}
      </p>
    </div>
  );
}
