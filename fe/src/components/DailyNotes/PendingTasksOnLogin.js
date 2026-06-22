import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckSquare, ClipboardCheck, ExternalLink, Loader2 } from 'lucide-react';

import { Button } from '../ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Badge } from '../ui/badge';
import { toast } from '../../utils/toast';
import { getStoredAuth, hasPermission, userMayEditFinancialFieldsFromStorage, PERSONA } from '../../utils/roleAccess';
import { useModuleSettings } from '../../hooks/useModuleSettings';
import { salesDailyNotesAccessEnabled } from '../../utils/dailyNotesAccess';
import {
  canToggleDailyTask,
  isPendingTasksPromptDismissed,
  markPendingTasksPromptDismissed,
} from '../../utils/dailyNotesTaskAccess';
import { formatDisplayDate } from '../../utils/dailyNotesTasks';
import { getPersonaFromStorage } from '../../utils/navAccess';
import { dailyTasksAPI } from '../../services/api';
import { dispatchNavBadgesRefresh, fetchNavBadgeCounts } from '../../utils/navBadges';

/**
 * After login, show a short summary of open tasks and pending approvals once per session.
 */
export default function PendingTasksOnLogin() {
  const navigate = useNavigate();
  const { user, permissions } = getStoredAuth();
  const persona = getPersonaFromStorage();
  const { settings: moduleSettings, loading: settingsLoading } = useModuleSettings('daily_notes');
  const [open, setOpen] = useState(false);
  const [tasks, setTasks] = useState([]);
  const [approvalCount, setApprovalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [togglingId, setTogglingId] = useState(null);

  const mayUseDailyNotes =
    hasPermission(permissions, 'daily_notes', 'view') &&
    (persona !== PERSONA.SALES || salesDailyNotesAccessEnabled(moduleSettings));

  const mayReviewApprovals = userMayEditFinancialFieldsFromStorage();

  const loadSummary = useCallback(async () => {
    if (isPendingTasksPromptDismissed()) {
      setLoading(false);
      return;
    }
    if (!mayUseDailyNotes && !mayReviewApprovals) {
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const counts = await fetchNavBadgeCounts({
        mayFetchTasks: mayUseDailyNotes && !settingsLoading,
        mayFetchApprovals: mayReviewApprovals,
      });

      let rows = [];
      if (mayUseDailyNotes && !settingsLoading && counts.pendingTasks > 0) {
        const res = await dailyTasksAPI.pending();
        rows = Array.isArray(res.data) ? res.data : [];
      }

      setTasks(rows);
      setApprovalCount(counts.pendingApprovals);
      if (rows.length > 0 || counts.pendingApprovals > 0) {
        setOpen(true);
      }
    } catch {
      setTasks([]);
      setApprovalCount(0);
    } finally {
      setLoading(false);
    }
  }, [mayReviewApprovals, mayUseDailyNotes, settingsLoading]);

  useEffect(() => {
    if (settingsLoading && mayUseDailyNotes) return;
    loadSummary();
  }, [settingsLoading, loadSummary, mayUseDailyNotes]);

  const handleDismiss = () => {
    markPendingTasksPromptDismissed();
    setOpen(false);
  };

  const handleGoToTasks = (taskDate) => {
    markPendingTasksPromptDismissed();
    setOpen(false);
    const query = taskDate ? `?date=${encodeURIComponent(taskDate)}` : '';
    navigate(`/daily-notes${query}`);
  };

  const handleGoToApprovals = () => {
    markPendingTasksPromptDismissed();
    setOpen(false);
    navigate('/pending-approvals');
  };

  const handleToggle = async (task) => {
    if (!canToggleDailyTask(task, user?.id)) return;
    setTogglingId(task.id);
    try {
      const res = await dailyTasksAPI.toggleDone(task.id);
      setTasks((prev) => {
        const next = prev
          .map((t) => (t.id === task.id ? res.data : t))
          .filter((t) => !t.is_done);
        if (next.length === 0 && approvalCount === 0) {
          setOpen(false);
          markPendingTasksPromptDismissed();
        }
        return next;
      });
      dispatchNavBadgesRefresh();
    } catch (error) {
      toast.error(error.response?.data?.error || 'Could not update task');
    } finally {
      setTogglingId(null);
    }
  };

  if (loading || !open || (tasks.length === 0 && approvalCount === 0)) {
    return null;
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && handleDismiss()}>
      <DialogContent
        className="max-h-[min(92dvh,100vh)] w-[calc(100%-1rem)] max-w-md overflow-hidden p-0 sm:w-full"
        description="Your open daily tasks and approvals waiting for review."
      >
        <DialogHeader className="border-b px-4 py-3">
          <DialogTitle className="text-base">Welcome back — here&apos;s your summary</DialogTitle>
          <div className="flex flex-wrap gap-2 pt-2">
            {tasks.length > 0 ? (
              <Badge variant="secondary" className="gap-1">
                <CheckSquare className="h-3.5 w-3.5" />
                {tasks.length} task{tasks.length !== 1 ? 's' : ''}
              </Badge>
            ) : null}
            {approvalCount > 0 ? (
              <Badge variant="secondary" className="gap-1">
                <ClipboardCheck className="h-3.5 w-3.5" />
                {approvalCount} approval{approvalCount !== 1 ? 's' : ''}
              </Badge>
            ) : null}
          </div>
        </DialogHeader>

        {tasks.length > 0 ? (
          <>
            <p className="px-4 pt-3 text-sm font-medium text-foreground">Your pending tasks</p>
            <ul className="max-h-[40dvh] divide-y overflow-y-auto">
              {tasks.map((task) => (
                <li key={task.id} className="flex items-start gap-3 px-4 py-3">
                  <input
                    type="checkbox"
                    className="mt-1 h-4 w-4 shrink-0"
                    checked={Boolean(task.is_done)}
                    disabled={togglingId === task.id}
                    onChange={() => handleToggle(task)}
                    aria-label={`Mark "${task.title}" done`}
                  />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-foreground">{task.title}</p>
                    {task.description ? (
                      <p className="mt-0.5 text-sm text-muted-foreground">{task.description}</p>
                    ) : null}
                    <p className="mt-1 text-xs text-muted-foreground">
                      Due {formatDisplayDate(task.task_date)}
                      {task.author_name ? ` · from ${task.author_name}` : ''}
                    </p>
                  </div>
                  {togglingId === task.id ? (
                    <Loader2 className="mt-1 h-4 w-4 shrink-0 animate-spin text-muted-foreground" />
                  ) : null}
                </li>
              ))}
            </ul>
          </>
        ) : null}

        {approvalCount > 0 ? (
          <div className="border-t px-4 py-3">
            <p className="text-sm text-muted-foreground">
              {approvalCount} change{approvalCount !== 1 ? 's' : ''} from your team need
              {approvalCount === 1 ? 's' : ''} your review before they go live.
            </p>
          </div>
        ) : null}

        <DialogFooter className="flex-col gap-2 border-t px-4 py-3 sm:flex-col">
          {tasks.length > 0 ? (
            <Button type="button" className="w-full" onClick={() => handleGoToTasks(tasks[0]?.task_date)}>
              <ExternalLink className="h-4 w-4" />
              Open daily notes
            </Button>
          ) : null}
          {approvalCount > 0 ? (
            <Button
              type="button"
              className="w-full"
              variant={tasks.length > 0 ? 'outline' : 'default'}
              onClick={handleGoToApprovals}
            >
              <ClipboardCheck className="h-4 w-4" />
              Review pending approvals
            </Button>
          ) : null}
          <Button type="button" variant="outline" className="w-full" onClick={handleDismiss}>
            Remind me later
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
