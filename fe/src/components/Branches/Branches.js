import React, { useState, useEffect } from 'react';
import { Plus } from 'lucide-react';
import { branchesAPI, usersAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import ConfirmDialog from '../ConfirmDialog/ConfirmDialog';
import SearchableSelect from '../Shared/SearchableSelect';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { PageShell, PageHeader, PageLoading, FilterBar, SearchField } from '../page';

const Branches = () => {
  const [branches, setBranches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [selectedBranch, setSelectedBranch] = useState(null);
  const [users, setUsers] = useState([]);
  const [formData, setFormData] = useState({
    branch_code: '',
    name: '',
    address: '',
    city: '',
    country: 'Kenya',
    phone: '',
    email: '',
    is_active: true,
    is_headquarters: false,
    manager: '',
    tenant_id: '',  // Will be set automatically from current tenant
  });
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    loadBranches();
    loadUsers();
  }, []);

  const loadBranches = async () => {
    setLoading(true);
    try {
      const response = await branchesAPI.list({ is_active: 'true' });
      const branchesData = response.data.results || response.data || [];
      setBranches(Array.isArray(branchesData) ? branchesData : []);
    } catch (error) {
      console.error('Error loading branches:', error);
      toast.error('Failed to load branches');
    } finally {
      setLoading(false);
    }
  };

  const loadUsers = async () => {
    try {
      const response = await usersAPI.list({ is_active: 'true' });
      const usersData = response.data.results || response.data || [];
      setUsers(Array.isArray(usersData) ? usersData : []);
    } catch (error) {
      console.error('Error loading users:', error);
    }
  };

  const handleCreate = () => {
    setSelectedBranch(null);
    setFormData({
      branch_code: '',
      name: '',
      address: '',
      city: '',
      country: 'Kenya',
      phone: '',
      email: '',
      is_active: true,
      is_headquarters: false,
      manager: '',
    });
    setShowModal(true);
  };

  const handleEdit = (branch) => {
    setSelectedBranch(branch);
    setFormData({
      branch_code: branch.branch_code || '',
      name: branch.name || '',
      address: branch.address || '',
      city: branch.city || '',
      country: branch.country || 'Kenya',
      phone: branch.phone || '',
      email: branch.email || '',
      is_active: branch.is_active !== undefined ? branch.is_active : true,
      is_headquarters: branch.is_headquarters || false,
      manager: branch.manager || '',
    });
    setShowModal(true);
  };

  const handleDelete = (branch) => {
    setSelectedBranch(branch);
    setShowDeleteConfirm(true);
  };

  const confirmDelete = async () => {
    if (!selectedBranch) return;
    
    try {
      await branchesAPI.delete(selectedBranch.id);
      toast.success('Branch deleted successfully');
      loadBranches();
      setShowDeleteConfirm(false);
      setSelectedBranch(null);
    } catch (error) {
      toast.error('Failed to delete branch: ' + (error.response?.data?.error || error.message));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    try {
      const branchData = {
        ...formData,
        manager: formData.manager || null,
      };
      
      if (selectedBranch) {
        await branchesAPI.update(selectedBranch.id, branchData);
        toast.success('Branch updated successfully');
      } else {
        await branchesAPI.create(branchData);
        toast.success('Branch created successfully');
      }
      setShowModal(false);
      loadBranches();
      setSelectedBranch(null);
    } catch (error) {
      toast.error('Failed to save branch: ' + (error.response?.data?.error || error.message));
    }
  };

  const filteredBranches = branches.filter(branch => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      branch.name.toLowerCase().includes(query) ||
      branch.branch_code.toLowerCase().includes(query) ||
      (branch.city && branch.city.toLowerCase().includes(query))
    );
  });

  return (
    <PageShell>
        <PageHeader title="Branch management" description="Manage branches and locations.">
          <Button onClick={handleCreate}>
            <Plus className="h-4 w-4" />
            Create branch
          </Button>
        </PageHeader>

        <FilterBar>
          <SearchField
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search branches…"
            className="min-w-[200px] flex-[2]"
          />
        </FilterBar>

        {loading ? (
          <PageLoading rows={6} />
        ) : (
          <div className="overflow-x-auto rounded-lg border bg-card shadow-sm">
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/40 text-left">
                <tr>
                  <th className="px-3 py-2 font-medium">Branch code</th>
                  <th className="px-3 py-2 font-medium">Name</th>
                  <th className="px-3 py-2 font-medium">Location</th>
                  <th className="px-3 py-2 font-medium">Manager</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Type</th>
                  <th className="px-3 py-2 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredBranches.length === 0 ? (
                  <tr>
                    <td colSpan="7" className="px-3 py-8 text-center text-muted-foreground">
                      No branches found
                    </td>
                  </tr>
                ) : (
                  filteredBranches.map((branch) => (
                    <tr key={branch.id} className="border-b last:border-0 hover:bg-muted/30">
                      <td className="px-3 py-2 font-medium">{branch.branch_code}</td>
                      <td className="px-3 py-2">{branch.name}</td>
                      <td className="px-3 py-2">
                        {[branch.city, branch.country].filter(Boolean).join(', ') || '—'}
                      </td>
                      <td className="px-3 py-2">{branch.manager_name || 'N/A'}</td>
                      <td className="px-3 py-2">
                        <Badge variant={branch.is_active ? 'success' : 'secondary'}>
                          {branch.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </td>
                      <td className="px-3 py-2">
                        {branch.is_headquarters ? (
                          <Badge variant="outline">Headquarters</Badge>
                        ) : null}
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex justify-end gap-1">
                          <Button type="button" variant="outline" size="sm" onClick={() => handleEdit(branch)}>
                            Edit
                          </Button>
                          <Button
                            type="button"
                            variant="destructive"
                            size="sm"
                            onClick={() => handleDelete(branch)}
                          >
                            Delete
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Branch Modal */}
        {showModal && (
          <div className="slide-in-overlay" onClick={() => setShowModal(false)}>
            <div className="slide-in-panel" onClick={(e) => e.stopPropagation()}>
              <div className="slide-in-panel-header">
                <h2>{selectedBranch ? 'Edit Branch' : 'Create Branch'}</h2>
                <button onClick={() => setShowModal(false)} className="slide-in-panel-close">×</button>
              </div>
              <div className="slide-in-panel-body">
                <form onSubmit={handleSubmit}>
                <div className="form-row">
                  <div className="form-group">
                    <label>Branch Code *</label>
                    <input
                      type="text"
                      value={formData.branch_code}
                      onChange={(e) => setFormData({ ...formData, branch_code: e.target.value })}
                      required
                      placeholder="e.g., BR001"
                    />
                  </div>
                  <div className="form-group">
                    <label>Branch Name *</label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      required
                      placeholder="e.g., Nairobi Main Branch"
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label>Address</label>
                  <textarea
                    value={formData.address}
                    onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                    rows="2"
                    placeholder="Street address"
                  />
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>City</label>
                    <input
                      type="text"
                      value={formData.city}
                      onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                      placeholder="City"
                    />
                  </div>
                  <div className="form-group">
                    <label>Country</label>
                    <input
                      type="text"
                      value={formData.country}
                      onChange={(e) => setFormData({ ...formData, country: e.target.value })}
                      placeholder="Country"
                    />
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label>Phone</label>
                    <input
                      type="text"
                      value={formData.phone}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                      placeholder="Phone number"
                    />
                  </div>
                  <div className="form-group">
                    <label>Email</label>
                    <input
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      placeholder="Email address"
                    />
                  </div>
                </div>
                <div className="form-group">
                  <label>Manager</label>
                  <SearchableSelect
                    value={formData.manager}
                    onChange={(e) => setFormData({ ...formData, manager: e.target.value })}
                    options={users.map(user => ({
                      id: user.id,
                      name: `${user.username}${user.first_name ? ` (${user.first_name} ${user.last_name || ''})` : ''}`
                    }))}
                    placeholder="Select Manager"
                  />
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={formData.is_active}
                        onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                      />
                      <span>Active</span>
                    </label>
                  </div>
                  <div className="form-group">
                    <label className="checkbox-label">
                      <input
                        type="checkbox"
                        checked={formData.is_headquarters}
                        onChange={(e) => setFormData({ ...formData, is_headquarters: e.target.checked })}
                      />
                      <span>Headquarters</span>
                    </label>
                  </div>
                </div>
                <div className="slide-in-panel-footer">
                  <button type="button" onClick={() => setShowModal(false)} className="btn btn-secondary">
                    Cancel
                  </button>
                  <button type="submit" className="btn btn-primary">
                    {selectedBranch ? 'Update' : 'Create'}
                  </button>
                </div>
                </form>
              </div>
            </div>
          </div>
        )}

        {/* Delete Confirm Dialog */}
        <ConfirmDialog
          isOpen={showDeleteConfirm}
          title="Delete Branch"
          message={`Are you sure you want to delete branch ${selectedBranch?.name}? This action cannot be undone.`}
          onConfirm={confirmDelete}
          onCancel={() => {
            setShowDeleteConfirm(false);
            setSelectedBranch(null);
          }}
          confirmText="Delete"
          cancelText="Cancel"
          type="danger"
        />
    </PageShell>
  );
};

export default Branches;
