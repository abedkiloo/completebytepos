import React, { useEffect, useState } from 'react';
import { dailyNotesAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { dateMessage, required } from '../../utils/formValidation';
import {
  clearFormBanner,
  reportFormError,
  reportFormWarning,
} from '../../utils/formFeedback';
import FormBanner from '../form/FormBanner';

const DailyNoteForm = ({
  note,
  defaultDate,
  canAssignToOthers = false,
  defaultAssignMode = 'person',
  onClose,
  onSave,
}) => {
  const [formData, setFormData] = useState({
    note_date: defaultDate || new Date().toISOString().slice(0, 10),
    title: '',
    content: '',
    is_sticky: false,
    assigned_to: '',
    assigned_role: '',
  });
  const [checklist, setChecklist] = useState([]);
  const [staff, setStaff] = useState([]);
  const [roles, setRoles] = useState([]);
  const [assignMode, setAssignMode] = useState(defaultAssignMode || 'person');
  const [loadingStaff, setLoadingStaff] = useState(false);
  const [loading, setLoading] = useState(false);
  const [formBanner, setFormBanner] = useState(null);

  useEffect(() => {
    if (note) {
      setFormData({
        note_date: note.note_date,
        title: note.title || '',
        content: note.content || '',
        is_sticky: Boolean(note.is_sticky),
        assigned_to: note.assigned_to ? String(note.assigned_to) : '',
        assigned_role: note.assigned_role ? String(note.assigned_role) : '',
      });
      setChecklist(
        Array.isArray(note.checklist_items)
          ? note.checklist_items.map((item, index) => ({
              key: String(item.id || `row-${index}`),
              id: item.id || null,
              label: item.label || '',
              is_done: Boolean(item.is_done),
            }))
          : []
      );
      if (note.assigned_role && !note.assigned_to) {
        setAssignMode('role');
      } else {
        setAssignMode('person');
      }
    } else if (defaultDate) {
      setFormData((prev) => ({ ...prev, note_date: defaultDate }));
      setChecklist([]);
    }
  }, [note, defaultDate]);

  useEffect(() => {
    if (note) return;
    if (defaultAssignMode === 'everyone' || defaultAssignMode === 'role' || defaultAssignMode === 'person') {
      setAssignMode(defaultAssignMode);
    }
  }, [defaultAssignMode, note]);

  useEffect(() => {
    if (!canAssignToOthers) return;
    let cancelled = false;
    setLoadingStaff(true);
    dailyNotesAPI
      .staff()
      .then((res) => {
        if (cancelled) return;
        const rows = Array.isArray(res.data) ? res.data : [];
        setStaff(rows);
      })
      .catch(() => {
        if (!cancelled) setStaff([]);
      });
    dailyNotesAPI
      .roles()
      .then((res) => {
        if (cancelled) return;
        const rows = Array.isArray(res.data) ? res.data : [];
        setRoles(rows);
      })
      .catch(() => {
        if (!cancelled) setRoles([]);
      })
      .finally(() => {
        if (!cancelled) setLoadingStaff(false);
      });
    return () => {
      cancelled = true;
    };
  }, [canAssignToOthers]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const dateErr = dateMessage(formData.note_date, { label: 'note date' });
    if (dateErr) {
      reportFormWarning(setFormBanner, dateErr);
      return;
    }
    const contentErr = required(
      formData.content,
      'Write the note, e.g. Stock count completed at close of day'
    );
    if (contentErr) {
      reportFormWarning(setFormBanner, contentErr);
      return;
    }
    if (formData.is_sticky && canAssignToOthers) {
      const hasPerson = assignMode === 'person' && formData.assigned_to;
      const hasRole = assignMode === 'role' && formData.assigned_role;
      const hasEveryone = assignMode === 'everyone' && !note;
      if (!hasPerson && !hasRole && !hasEveryone) {
        reportFormWarning(
          setFormBanner,
          'Assign this note to a person, a role, or everyone.'
        );
        return;
      }
    }
    const checklistItems = checklist
      .map((row, index) => ({
        label: String(row.label || '').trim(),
        is_done: Boolean(row.is_done),
        sort_order: index,
      }))
      .filter((row) => row.label);

    setLoading(true);
    try {
      const payload = {
        note_date: formData.note_date,
        title: formData.title.trim(),
        content: formData.content.trim(),
        is_sticky: Boolean(formData.is_sticky),
        checklist_items: checklistItems,
      };
      if (canAssignToOthers && assignMode === 'person' && formData.assigned_to) {
        payload.assigned_to = parseInt(formData.assigned_to, 10);
      }
      if (canAssignToOthers && assignMode === 'role' && formData.assigned_role) {
        payload.assigned_role = parseInt(formData.assigned_role, 10);
      }
      if (canAssignToOthers && assignMode === 'everyone' && !note) {
        payload.assign_to_all = true;
      }
      if (note?.id) {
        await dailyNotesAPI.update(note.id, payload);
        toast.success('Note updated');
      } else {
        const created = await dailyNotesAPI.create(payload);
        const createdCount = created?.data?.created_count || 1;
        toast.success(
          createdCount > 1
            ? `Note sent to ${createdCount} people`
            : payload.is_sticky
              ? 'Must-tick note saved'
              : 'Note saved'
        );
      }
      onSave();
    } catch (error) {
      const msg =
        error.response?.data?.error ||
        Object.values(error.response?.data || {}).flat().join(', ') ||
        'Failed to save note';
      reportFormError(setFormBanner, msg);
    } finally {
      setLoading(false);
    }
  };

  const userLabel = (u) => u.display_name || u.username;
  const showEveryone = canAssignToOthers && !note;

  return (
    <div className="slide-in-overlay" onClick={onClose}>
      <div className="slide-in-panel" onClick={(e) => e.stopPropagation()}>
        <div className="slide-in-panel-header">
          <h2>{note ? 'Edit note' : 'Add note'}</h2>
          <button type="button" onClick={onClose} className="slide-in-panel-close">
            ×
          </button>
        </div>
        <form
          onSubmit={(e) => {
            clearFormBanner(setFormBanner);
            handleSubmit(e);
          }}
          className="flex min-h-0 flex-1 flex-col overflow-hidden"
          data-testid="daily-note-form"
        >
          <div className="slide-in-panel-body">
            <FormBanner
              message={formBanner?.message}
              type={formBanner?.type || 'error'}
              onDismiss={() => clearFormBanner(setFormBanner)}
            />
            <div className="form-group">
              <label>Date *</label>
              <input
                type="date"
                name="note_date"
                value={formData.note_date}
                onChange={handleChange}
                required
                data-testid="note-date"
              />
            </div>
            <div className="form-group">
              <label>Title (optional)</label>
              <input
                type="text"
                name="title"
                value={formData.title}
                onChange={handleChange}
                placeholder="e.g. Opening shift, stock issue"
                maxLength={200}
              />
            </div>
            <div className="form-group">
              <label>Note *</label>
              <textarea
                name="content"
                value={formData.content}
                onChange={handleChange}
                rows={6}
                required
                placeholder="What happened today? Handover, incidents, follow-ups…"
                data-testid="note-content"
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Required. You can also add an optional checklist below.
              </p>
            </div>
            <div className="form-group" data-testid="note-checklist">
              <div className="mb-2 flex items-center justify-between gap-2">
                <label className="mb-0">Checklist (optional)</label>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  data-testid="note-checklist-add"
                  onClick={() =>
                    setChecklist((prev) => [
                      ...prev,
                      {
                        key: `new-${Date.now()}-${prev.length}`,
                        id: null,
                        label: '',
                        is_done: false,
                      },
                    ])
                  }
                >
                  Add item
                </button>
              </div>
              {checklist.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No checklist items. Add ones for things to tick off with this note.
                </p>
              ) : (
                <ul className="space-y-2">
                  {checklist.map((row, index) => (
                    <li key={row.key} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        className="h-4 w-4 shrink-0"
                        checked={Boolean(row.is_done)}
                        onChange={(e) =>
                          setChecklist((prev) =>
                            prev.map((item, i) =>
                              i === index ? { ...item, is_done: e.target.checked } : item
                            )
                          )
                        }
                        aria-label={`Checklist item ${index + 1} done`}
                      />
                      <input
                        type="text"
                        className="min-w-0 flex-1"
                        value={row.label}
                        maxLength={200}
                        placeholder="e.g. Count till, lock store"
                        data-testid={`note-checklist-label-${index}`}
                        onChange={(e) =>
                          setChecklist((prev) =>
                            prev.map((item, i) =>
                              i === index ? { ...item, label: e.target.value } : item
                            )
                          )
                        }
                      />
                      <button
                        type="button"
                        className="btn btn-secondary btn-sm"
                        data-testid={`note-checklist-remove-${index}`}
                        onClick={() =>
                          setChecklist((prev) => prev.filter((_, i) => i !== index))
                        }
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="form-checkboxes">
              <label>
                <input
                  type="checkbox"
                  name="is_sticky"
                  checked={formData.is_sticky}
                  onChange={handleChange}
                  data-testid="note-is-sticky"
                />
                Must tick — the person assigned cannot use the system until they tick this
              </label>
            </div>
            {canAssignToOthers ? (
              <div className="form-group">
                <label>Assign to</label>
                <div className="flex flex-wrap gap-3 mb-2">
                  <label className="flex items-center gap-1 text-sm">
                    <input
                      type="radio"
                      name="assign_mode"
                      value="person"
                      checked={assignMode === 'person'}
                      onChange={() => setAssignMode('person')}
                      data-testid="note-assign-person"
                    />
                    Someone
                  </label>
                  <label className="flex items-center gap-1 text-sm">
                    <input
                      type="radio"
                      name="assign_mode"
                      value="role"
                      checked={assignMode === 'role'}
                      onChange={() => setAssignMode('role')}
                      data-testid="note-assign-role"
                    />
                    Everyone in a role
                  </label>
                  {showEveryone ? (
                    <label className="flex items-center gap-1 text-sm">
                      <input
                        type="radio"
                        name="assign_mode"
                        value="everyone"
                        checked={assignMode === 'everyone'}
                        onChange={() => setAssignMode('everyone')}
                        data-testid="note-assign-everyone"
                      />
                      Everyone
                    </label>
                  ) : null}
                </div>
                {assignMode === 'person' ? (
                  <select
                    name="assigned_to"
                    value={formData.assigned_to}
                    onChange={handleChange}
                    disabled={loadingStaff}
                    data-testid="note-assigned-to"
                  >
                    <option value="">Select staff member…</option>
                    {staff.map((u) => (
                      <option key={u.id} value={u.id}>
                        {userLabel(u)}
                      </option>
                    ))}
                  </select>
                ) : assignMode === 'role' ? (
                  <select
                    name="assigned_role"
                    value={formData.assigned_role}
                    onChange={handleChange}
                    disabled={loadingStaff}
                    data-testid="note-assigned-role"
                  >
                    <option value="">Select role…</option>
                    {roles.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name}
                      </option>
                    ))}
                  </select>
                ) : (
                  <p className="text-sm text-muted-foreground" data-testid="note-assign-everyone-hint">
                    Sends a copy to every active staff member in the system.
                  </p>
                )}
                {formData.is_sticky ? (
                  <p className="text-sm text-muted-foreground mt-1">
                    Must-tick notes need a person, a role, or everyone so someone can tick them.
                  </p>
                ) : null}
              </div>
            ) : null}
            {formData.is_sticky && !canAssignToOthers ? (
              <p className="text-sm text-muted-foreground">
                This note will block you until you tick it.
              </p>
            ) : null}
          </div>
          <div className="slide-in-panel-footer">
            <button type="button" onClick={onClose} className="btn btn-secondary">
              Cancel
            </button>
            <button type="submit" disabled={loading} className="btn btn-primary">
              {loading ? 'Saving…' : note ? 'Update' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default DailyNoteForm;
