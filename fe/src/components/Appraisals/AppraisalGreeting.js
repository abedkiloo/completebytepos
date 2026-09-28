import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Star } from 'lucide-react';

import { appraisalsAPI, dailyNotesAPI } from '../../services/api';
import { hasInboxNotes } from '../../utils/dailyNotesSticky';
import { getStoredAuth, hasPermission } from '../../utils/roleAccess';
import { Button } from '../ui/button';
import AppraisalProgressCard from './AppraisalProgressCard';

function dismissedKey(date) {
  return `appraisal-greeting-${date}`;
}

export default function AppraisalGreeting() {
  const navigate = useNavigate();
  const { permissions } = getStoredAuth();
  const canView = hasPermission(permissions, 'appraisals', 'view');
  const [snapshot, setSnapshot] = useState(null);
  const [open, setOpen] = useState(false);

  const load = useCallback(async () => {
    if (!canView) return;
    try {
      const [meRes, notesRes] = await Promise.all([
        appraisalsAPI.me(),
        dailyNotesAPI.blocking().catch(() => ({ data: [] })),
      ]);
      const notes = Array.isArray(notesRes.data) ? notesRes.data : [];
      const me = meRes.data;
      if (!me?.policy?.greet_when_no_sticky_notes) return;
      if (hasInboxNotes(notes.filter((n) => !n.is_done))) return;
      const today = me.today?.date;
      if (today && sessionStorage.getItem(dismissedKey(today))) return;
      setSnapshot(me);
      setOpen(true);
    } catch {
      setOpen(false);
    }
  }, [canView]);

  useEffect(() => {
    load();
  }, [load]);

  if (!open || !snapshot) return null;

  const dismiss = () => {
    if (snapshot.today?.date) {
      sessionStorage.setItem(dismissedKey(snapshot.today.date), '1');
    }
    setOpen(false);
  };

  return (
    <div
      className="fixed inset-0 z-[3100] flex items-center justify-center overflow-y-auto bg-black/55 p-4"
      data-testid="appraisal-greeting"
      role="dialog"
      aria-modal="true"
      aria-labelledby="appraisal-greeting-title"
    >
      <div className="my-auto w-full max-w-lg">
        <AppraisalProgressCard snapshot={snapshot} className="shadow-2xl" />
        <div className="mt-3 flex flex-wrap justify-end gap-2">
          <Button variant="outline" onClick={dismiss}>
            Continue
          </Button>
          <Button
            onClick={() => {
              dismiss();
              navigate('/appraisals');
            }}
          >
            <Star className="mr-1.5 h-4 w-4" />
            Open appraisals
          </Button>
        </div>
      </div>
    </div>
  );
}
