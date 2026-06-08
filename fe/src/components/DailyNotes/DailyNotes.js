import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Calendar, NotebookPen, Pencil, Plus, Trash2 } from 'lucide-react';
import { dailyNotesAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { getPersonaFromStorage, getStoredAuth } from '../../utils/roleAccess';
import { useModuleSettings } from '../../hooks/useModuleSettings';
import { userMayViewAllDailyNotes } from '../../utils/dailyNotesAccess';
import DailyNoteForm from './DailyNoteForm';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import { Button } from '../ui/button';
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

  const canModifyNote = (note) =>
    note.author === currentUserId || note.author_id === currentUserId;

  const [selectedDate, setSelectedDate] = useState(todayIso());
  const [recentDates, setRecentDates] = useState([]);
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingNote, setEditingNote] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);

  const loadRecentDates = useCallback(async () => {
    try {
      const res = await dailyNotesAPI.recentDates();
      setRecentDates(res.data?.dates || []);
    } catch {
      setRecentDates([]);
    }
  }, []);

  const loadNotes = useCallback(async () => {
    setLoading(true);
    try {
      const params = { note_date: selectedDate, page_size: 100 };
      const res = await dailyNotesAPI.list(params);
      const rows = res.data?.results || res.data || [];
      setNotes(Array.isArray(rows) ? rows : []);
    } catch (error) {
      console.error(error);
      setNotes([]);
      toast.error('Could not load notes for this date');
    } finally {
      setLoading(false);
    }
  }, [selectedDate]);

  useEffect(() => {
    loadRecentDates();
  }, [loadRecentDates]);

  useEffect(() => {
    loadNotes();
  }, [loadNotes]);

  const dateOptions = useMemo(() => {
    const set = new Set([selectedDate, todayIso(), ...recentDates]);
    return Array.from(set).sort((a, b) => (a < b ? 1 : -1));
  }, [recentDates, selectedDate]);

  const openCreate = () => {
    setEditingNote(null);
    setShowForm(true);
  };

  const openEdit = (note) => {
    setEditingNote(note);
    setShowForm(true);
  };

  const handleDelete = async () => {
    if (!confirmDelete) return;
    try {
      await dailyNotesAPI.delete(confirmDelete);
      toast.success('Note deleted');
      setConfirmDelete(null);
      loadNotes();
      loadRecentDates();
    } catch (error) {
      toast.error(error.response?.data?.error || 'Could not delete note');
    }
  };

  const handleSaved = () => {
    setShowForm(false);
    setEditingNote(null);
    loadNotes();
    loadRecentDates();
  };

  return (
    <PageShell>
      <PageHeader
        title="Daily notes"
        description={
          viewAll
            ? 'Journal entries from your team. Pick a date to review what was logged.'
            : 'Log what happened on a shift — your manager and admin can review team notes.'
        }
      >
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4" />
          Add note
        </Button>
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
          <label className="mb-1 block text-sm font-medium">Recent days with notes</label>
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
      ) : notes.length === 0 ? (
        <EmptyState
          icon={NotebookPen}
          title="No notes for this day"
          description="Add a note about opening, sales, stock, or anything worth remembering."
          action={
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4" />
              Add note
            </Button>
          }
        />
      ) : (
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
                  {canModifyNote(note) ? (
                    <div className="flex justify-end gap-1">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        title="Edit"
                        onClick={() => openEdit(note)}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        title="Delete"
                        onClick={() => setConfirmDelete(note.id)}
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
      )}

      {showForm && (
        <DailyNoteForm
          note={editingNote}
          defaultDate={selectedDate}
          onClose={() => {
            setShowForm(false);
            setEditingNote(null);
          }}
          onSave={handleSaved}
        />
      )}

      <ConfirmDialog
        isOpen={Boolean(confirmDelete)}
        title="Delete note?"
        message="This cannot be undone."
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(null)}
      />
    </PageShell>
  );
};

export default DailyNotes;
