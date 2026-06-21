import React, { useEffect, useState } from 'react';
import { dailyTasksAPI, usersAPI } from '../../services/api';
import { toast } from '../../utils/toast';

const DailyTaskForm = ({ task, defaultDate, canAssignToOthers = false, onClose, onSave }) => {
  const [formData, setFormData] = useState({
    task_date: defaultDate || new Date().toISOString().slice(0, 10),
    title: '',
    description: '',
    is_done: false,
    assigned_to: '',
  });
  const [users, setUsers] = useState([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (task) {
      setFormData({
        task_date: task.task_date,
        title: task.title || '',
        description: task.description || '',
        is_done: Boolean(task.is_done),
        assigned_to: task.assigned_to ? String(task.assigned_to) : '',
      });
    } else if (defaultDate) {
      setFormData((prev) => ({ ...prev, task_date: defaultDate }));
    }
  }, [task, defaultDate]);

  useEffect(() => {
    if (!canAssignToOthers) return;
    let cancelled = false;
    setLoadingUsers(true);
    usersAPI
      .list({ page_size: 200, is_active: true })
      .then((res) => {
        if (cancelled) return;
        const rows = res.data?.results || res.data || [];
        setUsers(Array.isArray(rows) ? rows : []);
      })
      .catch(() => {
        if (!cancelled) setUsers([]);
      })
      .finally(() => {
        if (!cancelled) setLoadingUsers(false);
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
    if (!formData.title.trim()) {
      toast.warning('Enter a task title.');
      return;
    }
    setLoading(true);
    try {
      const payload = {
        task_date: formData.task_date,
        title: formData.title.trim(),
        description: formData.description.trim(),
        is_done: formData.is_done,
      };
      if (canAssignToOthers && formData.assigned_to) {
        payload.assigned_to = parseInt(formData.assigned_to, 10);
      }
      if (task?.id) {
        await dailyTasksAPI.update(task.id, payload);
        toast.success('Task updated');
      } else {
        await dailyTasksAPI.create(payload);
        toast.success('Task added');
      }
      onSave();
    } catch (error) {
      const msg =
        error.response?.data?.error ||
        Object.values(error.response?.data || {}).flat().join(', ') ||
        'Failed to save task';
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const userLabel = (u) => {
    const name = [u.first_name, u.last_name].filter(Boolean).join(' ').trim();
    return name ? `${name} (${u.username})` : u.username;
  };

  return (
    <div className="slide-in-overlay" onClick={onClose}>
      <div className="slide-in-panel" onClick={(e) => e.stopPropagation()}>
        <div className="slide-in-panel-header">
          <h2>{task ? 'Edit task' : 'Add task'}</h2>
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
                name="task_date"
                value={formData.task_date}
                onChange={handleChange}
                required
              />
            </div>
            {canAssignToOthers && (
              <div className="form-group">
                <label>Assign to *</label>
                <select
                  name="assigned_to"
                  value={formData.assigned_to}
                  onChange={handleChange}
                  required={canAssignToOthers}
                  disabled={loadingUsers}
                >
                  <option value="">Select staff member…</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>
                      {userLabel(u)}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div className="form-group">
              <label>Task *</label>
              <input
                type="text"
                name="title"
                value={formData.title}
                onChange={handleChange}
                placeholder="e.g. Count cash drawer, restock shelf A"
                maxLength={200}
                required
              />
            </div>
            <div className="form-group">
              <label>Details (optional)</label>
              <textarea
                name="description"
                value={formData.description}
                onChange={handleChange}
                rows={4}
                placeholder="Extra context for whoever reads this later"
              />
            </div>
            <div className="form-checkboxes">
              <label>
                <input
                  type="checkbox"
                  name="is_done"
                  checked={formData.is_done}
                  onChange={handleChange}
                />
                Mark as done
              </label>
            </div>
          </div>
          <div className="slide-in-panel-footer">
            <button type="button" onClick={onClose} className="btn btn-secondary">
              Cancel
            </button>
            <button type="submit" disabled={loading} className="btn btn-primary">
              {loading ? 'Saving…' : task ? 'Update' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default DailyTaskForm;
