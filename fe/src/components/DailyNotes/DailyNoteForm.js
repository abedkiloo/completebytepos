import React, { useEffect, useState } from 'react';
import { dailyNotesAPI } from '../../services/api';
import { toast } from '../../utils/toast';

const DailyNoteForm = ({ note, defaultDate, onClose, onSave }) => {
  const [formData, setFormData] = useState({
    note_date: defaultDate || new Date().toISOString().slice(0, 10),
    title: '',
    content: '',
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (note) {
      setFormData({
        note_date: note.note_date,
        title: note.title || '',
        content: note.content || '',
      });
    } else if (defaultDate) {
      setFormData((prev) => ({ ...prev, note_date: defaultDate }));
    }
  }, [note, defaultDate]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.content.trim()) {
      toast.warning('Write something in the note.');
      return;
    }
    setLoading(true);
    try {
      const payload = {
        note_date: formData.note_date,
        title: formData.title.trim(),
        content: formData.content.trim(),
      };
      if (note?.id) {
        await dailyNotesAPI.update(note.id, payload);
        toast.success('Note updated');
      } else {
        await dailyNotesAPI.create(payload);
        toast.success('Note saved');
      }
      onSave();
    } catch (error) {
      const msg =
        error.response?.data?.error ||
        Object.values(error.response?.data || {}).flat().join(', ') ||
        'Failed to save note';
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="slide-in-overlay" onClick={onClose}>
      <div className="slide-in-panel" onClick={(e) => e.stopPropagation()}>
        <div className="slide-in-panel-header">
          <h2>{note ? 'Edit note' : 'Add note'}</h2>
          <button type="button" onClick={onClose} className="slide-in-panel-close">
            ×
          </button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="slide-in-panel-body">
            <div className="form-group">
              <label>Date *</label>
              <input
                type="date"
                name="note_date"
                value={formData.note_date}
                onChange={handleChange}
                required
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
                rows={8}
                required
                placeholder="What happened today? Handover, incidents, follow-ups…"
              />
            </div>
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
