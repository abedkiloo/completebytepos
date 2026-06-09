import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Calendar, CheckSquare, NotebookPen, Pencil, Plus, Trash2 } from 'lucide-react';
import { dailyNotesAPI, dailyTasksAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { getPersonaFromStorage, getStoredAuth } from '../../utils/roleAccess';
import { useModuleSettings } from '../../hooks/useModuleSettings';
import { userMayViewAllDailyNotes } from '../../utils/dailyNotesAccess';
import {
  countOpenTasks,
  formatTaskCompletedAt,
  sortDailyTasks,
  taskStatusLabel,
} from '../../utils/dailyNotesTasks';
import DailyNoteForm from './DailyNoteForm';
import DailyTaskForm from './DailyTaskForm';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import {
  PageShell,
  PageHeader,
  PageLoading,
  EmptyState,
  DataTable,
  DataTableHeader,
  DataTableHead,
  DataTableBody,
  DataTableRow,
  DataTableCell,
} from '../page';

const todayIso = () => new Date().toISOString().slice(0, 10);

const formatDisplayDate = (iso) => {
  if (!iso) return '';
  try {
    return new Date(`${iso}T12:00:00`).toLocaleDateString(undefined, {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return iso;
  }
};

const DailyNotes = () => {
  const persona = getPersonaFromStorage();
  const { user } = getStoredAuth();
  const currentUserId = user?.id;
  const { settings: moduleSettings } = useModuleSettings('daily_notes');
  const viewAll = userMayViewAllDailyNotes(persona, moduleSettings);

  const canModifyEntry = (entry) =>
    entry.author === currentUserId || entry.author_id === currentUserId;

  const [selectedDate, setSelectedDate] = useState(todayIso());
  const [recentDates, setRecentDates] = useState([]);
  const [notes, setNotes] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showNoteForm, setShowNoteForm] = useState(false);
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [editingNote, setEditingNote] = useState(null);
  const [editingTask, setEditingTask] = useState(null);
  const [confirmDeleteNote, setConfirmDeleteNote] = useState(null);
  const [confirmDeleteTask, setConfirmDeleteTask] = useState(null);
  const [togglingTaskId, setTogglingTaskId] = useState(null);

  const sortedTasks = useMemo(() => sortDailyTasks(tasks), [tasks]);
  const openTaskCount = useMemo(() => countOpenTasks(tasks), [tasks]);

  const loadRecentDates = useCallback(async () => {
    try {
      const res = await dailyNotesAPI.recentDates();
      setRecentDates(res.data?.dates || []);
    } catch {
      setRecentDates([]);
    }
  }, []);

  const loadDay = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page_size: 100 };
      const noteParams = { ...params, note_date: selectedDate };
      const taskParams = { ...params, task_date: selectedDate };
      const [notesRes, tasksRes] = await Promise.all([
        dailyNotesAPI.list(noteParams),
        dailyTasksAPI.list(taskParams),
      ]);
      const noteRows = notesRes.data?.results || notesRes.data || [];
      const taskRows = tasksRes.data?.results || tasksRes.data || [];
      setNotes(Array.isArray(noteRows) ? noteRows : []);
      setTasks(Array.isArray(taskRows) ? taskRows : []);
    } catch (error) {
      console.error(error);
      setNotes([]);
      setTasks([]);
      toast.error('Could not load this day');
    } finally {
      setLoading(false);
    }
  }, [selectedDate]);

  useEffect(() => {
    loadRecentDates();
  }, [loadRecentDates]);

  useEffect(() => {
    loadDay();
  }, [loadDay]);

  const dateOptions = useMemo(() => {
    const set = new Set([selectedDate, todayIso(), ...recentDates]);
    return Array.from(set).sort((a, b) => (a < b ? 1 : -1));
  }, [recentDates, selectedDate]);

  const refreshAll = () => {
    loadDay();
    loadRecentDates();
  };

  const handleToggleTask = async (task) => {
    if (!canModifyEntry(task)) return;
    setTogglingTaskId(task.id);
    try {
      const res = await dailyTasksAPI.toggleDone(task.id);
      setTasks((prev) => prev.map((t) => (t.id === task.id ? res.data : t)));
    } catch (error) {
      toast.error(error.response?.data?.error || 'Could not update task');
    } finally {
      setTogglingTaskId(null);
    }
  };

  const handleDeleteNote = async () => {
    if (!confirmDeleteNote) return;
    try {
      await dailyNotesAPI.delete(confirmDeleteNote);
      toast.success('Note deleted');
      setConfirmDeleteNote(null);
      refreshAll();
    } catch (error) {
      toast.error(error.response?.data?.error || 'Could not delete note');
    }
  };

  const handleDeleteTask = async () => {
    if (!confirmDeleteTask) return;
    try {
      await dailyTasksAPI.delete(confirmDeleteTask);
      toast.success('Task deleted');
      setConfirmDeleteTask(null);
      refreshAll();
    } catch (error) {
      toast.error(error.response?.data?.error || 'Could not delete task');
    }
  };

  const isEmpty = !loading && notes.length === 0 && tasks.length === 0;

  return (
    <PageShell>
      <PageHeader
        title="Daily notes"
        description={
          viewAll
            ? 'Tasks and journal entries for your team. Pick a date to see what was planned and logged.'
            : 'Track tasks and log shift notes — managers and admin can review the team journal.'
        }
      >
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            onClick={() => {
              setEditingTask(null);
              setShowTaskForm(true);
            }}
          >
            <Plus className="h-4 w-4" />
            Add task
          </Button>
          <Button
            onClick={() => {
              setEditingNote(null);
              setShowNoteForm(true);
            }}
          >
            <Plus className="h-4 w-4" />
            Add note
          </Button>
        </div>
      </PageHeader>

      <div className="mb-4 flex flex-col gap-3 rounded-lg border bg-card p-4 sm:flex-row sm:items-end">
        <div className="form-group flex-1">
          <label className="mb-1 flex items-center gap-2 text-sm font-medium">
            <Calendar className="h-4 w-4" />
            Date
          </label>
          <input
            type="date"
            className="w-full max-w-xs"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
          />
        </div>
        <div className="form-group flex-1">
          <label className="mb-1 block text-sm font-medium">Recent days with activity</label>
          <select
            className="w-full max-w-xs"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
          >
            {dateOptions.map((d) => (
              <option key={d} value={d}>
                {formatDisplayDate(d)}
                {d === todayIso() ? ' (today)' : ''}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <PageLoading rows={5} />
      ) : isEmpty ? (
        <EmptyState
          icon={NotebookPen}
          title="Nothing for this day yet"
          description="Add tasks to track what should be done, and notes to record what happened."
          action={
            <div className="flex flex-wrap justify-center gap-2">
              <Button
                variant="outline"
                onClick={() => {
                  setEditingTask(null);
                  setShowTaskForm(true);
                }}
              >
                <Plus className="h-4 w-4" />
                Add task
              </Button>
              <Button
                onClick={() => {
                  setEditingNote(null);
                  setShowNoteForm(true);
                }}
              >
                <Plus className="h-4 w-4" />
                Add note
              </Button>
            </div>
          }
        />
      ) : (
        <div className="space-y-8">
          <section>
              <div className="mb-3 flex items-center justify-between gap-2">
                <h2 className="flex items-center gap-2 text-sm font-medium uppercase tracking-wide text-muted-foreground">
                  <CheckSquare className="h-4 w-4" />
                  Tasks
                  {openTaskCount > 0 && (
                    <Badge variant="secondary">{openTaskCount} open</Badge>
                  )}
                </h2>
              </div>
              {tasks.length === 0 ? (
                <p className="text-sm text-muted-foreground">No tasks for this date.</p>
              ) : (
                <ul className="divide-y rounded-lg border bg-card">
                  {sortedTasks.map((task) => (
                    <li
                      key={task.id}
                      className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-start sm:justify-between"
                    >
                      <div className="flex min-w-0 flex-1 items-start gap-3">
                        <input
                          type="checkbox"
                          className="mt-1 h-4 w-4 shrink-0"
                          checked={Boolean(task.is_done)}
                          disabled={!canModifyEntry(task) || togglingTaskId === task.id}
                          onChange={() => handleToggleTask(task)}
                          aria-label={`Mark "${task.title}" done`}
                        />
                        <div className="min-w-0">
                          <p
                            className={`font-medium ${task.is_done ? 'text-muted-foreground line-through' : ''}`}
                          >
                            {task.title}
                          </p>
                          {task.description ? (
                            <p className="mt-1 whitespace-pre-wrap text-sm text-muted-foreground">
                              {task.description}
                            </p>
                          ) : null}
                          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                            {viewAll && (
                              <span>{task.author_name || task.author_username}</span>
                            )}
                            <span>{taskStatusLabel(task)}</span>
                            {task.is_done && task.completed_at && (
                              <span title={formatTaskCompletedAt(task.completed_at)}>
                                ✓
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                      {canModifyEntry(task) && (
                        <div className="flex shrink-0 justify-end gap-1">
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            title="Edit"
                            onClick={() => {
                              setEditingTask(task);
                              setShowTaskForm(true);
                            }}
                          >
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            title="Delete"
                            onClick={() => setConfirmDeleteTask(task.id)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>

          {notes.length > 0 && (
            <section>
              <h2 className="mb-3 flex items-center gap-2 text-sm font-medium uppercase tracking-wide text-muted-foreground">
                <NotebookPen className="h-4 w-4" />
                Notes
              </h2>
              <DataTable>
                <DataTableHeader>
                  <tr>
                    {viewAll && <DataTableHead>Author</DataTableHead>}
                    <DataTableHead>Title</DataTableHead>
                    <DataTableHead>Note</DataTableHead>
                    <DataTableHead>Updated</DataTableHead>
                    <DataTableHead className="w-24 text-right">Actions</DataTableHead>
                  </tr>
                </DataTableHeader>
                <DataTableBody>
                  {notes.map((note) => (
                    <DataTableRow key={note.id}>
                      {viewAll && (
                        <DataTableCell className="whitespace-nowrap text-sm text-muted-foreground">
                          {note.author_name || note.author_username}
                        </DataTableCell>
                      )}
                      <DataTableCell className="font-medium">
                        {note.title || '—'}
                      </DataTableCell>
                      <DataTableCell>
                        <p className="whitespace-pre-wrap text-sm">{note.content}</p>
                      </DataTableCell>
                      <DataTableCell className="whitespace-nowrap text-sm text-muted-foreground">
                        {note.updated_at
                          ? new Date(note.updated_at).toLocaleString()
                          : '—'}
                      </DataTableCell>
                      <DataTableCell className="text-right">
                        {canModifyEntry(note) ? (
                          <div className="flex justify-end gap-1">
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              title="Edit"
                              onClick={() => {
                                setEditingNote(note);
                                setShowNoteForm(true);
                              }}
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              title="Delete"
                              onClick={() => setConfirmDeleteNote(note.id)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </DataTableCell>
                    </DataTableRow>
                  ))}
                </DataTableBody>
              </DataTable>
            </section>
          )}
        </div>
      )}

      {showNoteForm && (
        <DailyNoteForm
          note={editingNote}
          defaultDate={selectedDate}
          onClose={() => {
            setShowNoteForm(false);
            setEditingNote(null);
          }}
          onSave={() => {
            setShowNoteForm(false);
            setEditingNote(null);
            refreshAll();
          }}
        />
      )}

      {showTaskForm && (
        <DailyTaskForm
          task={editingTask}
          defaultDate={selectedDate}
          onClose={() => {
            setShowTaskForm(false);
            setEditingTask(null);
          }}
          onSave={() => {
            setShowTaskForm(false);
            setEditingTask(null);
            refreshAll();
          }}
        />
      )}

      <ConfirmDialog
        isOpen={Boolean(confirmDeleteNote)}
        title="Delete note?"
        message="This cannot be undone."
        onConfirm={handleDeleteNote}
        onCancel={() => setConfirmDeleteNote(null)}
      />

      <ConfirmDialog
        isOpen={Boolean(confirmDeleteTask)}
        title="Delete task?"
        message="This cannot be undone."
        onConfirm={handleDeleteTask}
        onCancel={() => setConfirmDeleteTask(null)}
      />
    </PageShell>
  );
};

export default DailyNotes;
