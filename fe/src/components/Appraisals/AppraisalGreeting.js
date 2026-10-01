import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Star } from 'lucide-react';

import { appraisalsAPI, dailyNotesAPI } from '../../services/api';
import { hasInboxNotes } from '../../utils/dailyNotesSticky';
import { getStoredAuth, hasPermission } from '../../utils/roleAccess';
import { canShowAppraisalGreetingOverlay } from '../../utils/loginOverlayQueue';
import { useLoginOverlayState } from '../../hooks/useLoginOverlay';
import { Button } from '../ui/button';
import AppraisalProgressCard from './AppraisalProgressCard';

function dismissedKey(date) {
  return `appraisal-greeting-${date}`;
}

export default function AppraisalGreeting() {
  const navigate = useNavigate();
  const { permissions } = getStoredAuth();
  const canView = hasPermission(permissions, 'appraisals', 'view');
  const overlay = useLoginOverlayState();
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

  if (!open || !snapshot || !canShowAppraisalGreetingOverlay(overlay)) return null;

  const dismiss = () => {
    if (snapshot.today?.date) {
      sessionStorage.setItem(dismissedKey(snapshot.today.date), '1');
    }
    setOpen(false);
  };

  return (
    <div
      className="fixed inset-0 z-[3100] flex items-center justify-center overflow-y-auto bg-[#080c14]/92 p-4 backdrop-blur-[2px]"
      data-testid="appraisal-greeting"
      role="dialog"
      aria-modal="true"
      aria-labelledby="appraisal-greeting-title"
    >
      <div className="my-auto w-full max-w-xl">
        <AppraisalProgressCard
          snapshot={snapshot}
          emphasis
          actions={(
            <>
              <Button
                variant="outline"
                className="border-white/40 bg-transparent text-white hover:bg-white/10 hover:text-white"
                onClick={dismiss}
              >
                Continue
              </Button>
              <Button
                className="bg-amber-400 text-slate-950 hover:bg-amber-300"
                onClick={() => {
                  dismiss();
                  navigate('/appraisals');
                }}
              >
                <Star className="mr-1.5 h-4 w-4" />
                Open my progress
              </Button>
            </>
          )}
        />
      </div>
    </div>
  );
}
