import React, { useCallback, useEffect, useState } from 'react';
import { Inbox } from 'lucide-react';
import { cmsAPI } from '../../services/api';
import { useDebouncedValue } from '../../hooks/useDebouncedValue';
import { toast } from '../../utils/toast';
import { Button } from '../ui/button';
import {
  EmptyState,
  FilterBar,
  FilterPills,
  PageHeader,
  PageLoading,
  PageShell,
  SearchField,
  StatusBadge,
} from '../page';
import { apiErrorMessage } from './blogPostHelpers';

const STATUS_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'new', label: 'New' },
  { value: 'reviewed', label: 'Reviewed' },
  { value: 'closed', label: 'Closed' },
];

const STATUS_LABEL = { new: 'New', reviewed: 'Reviewed', closed: 'Closed' };

const formatDate = (value) =>
  value
    ? new Date(value).toLocaleString('en-KE', {
        day: 'numeric',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
      })
    : '—';

const WebsiteEnquiries = () => {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState('new');
  const [search, setSearch] = useState('');
  const debouncedSearch = useDebouncedValue(search);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page_size: 100 };
      if (status) params.status = status;
      if (debouncedSearch) params.search = debouncedSearch;
      const res = await cmsAPI.listEnquiries(params);
      const list = res.data?.results ?? res.data ?? [];
      setRows(Array.isArray(list) ? list : []);
    } catch (error) {
      toast.error(apiErrorMessage(error, 'Failed to load enquiries'));
    } finally {
      setLoading(false);
    }
  }, [status, debouncedSearch]);

  useEffect(() => {
    load();
  }, [load]);

  const setEnquiryStatus = async (row, next) => {
    try {
      await cmsAPI.updateEnquiry(row.id, { status: next });
      toast.success(next === 'reviewed' ? 'Marked as reviewed' : 'Enquiry closed');
      load();
    } catch (error) {
      toast.error(apiErrorMessage(error, 'Could not update the enquiry.'));
    }
  };

  if (loading && rows.length === 0 && status === 'new' && !debouncedSearch) {
    return <PageLoading rows={5} />;
  }

  return (
    <PageShell>
      <PageHeader
        title="Website enquiries"
        description="Requests sent from omuwenga.com. Review them here, then reply on the phone number they left."
      />
      <FilterBar>
        <SearchField
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search name, phone or fitting…"
        />
        <FilterPills options={STATUS_OPTIONS} value={status} onChange={setStatus} />
      </FilterBar>
      {rows.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title="No enquiries in this view"
          description="When someone sends a request from the website, it appears here."
        />
      ) : (
        <div className="overflow-x-auto rounded-lg border bg-card shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="text-left">From</th>
                <th className="text-left">Fitting</th>
                <th className="text-left">Message</th>
                <th className="text-left">Status</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>
                    <div className="font-medium">{row.name}</div>
                    <div className="text-xs text-muted-foreground">{row.phone}</div>
                    <div className="text-xs text-muted-foreground">
                      {[row.business, row.location].filter(Boolean).join(' · ') || formatDate(row.created_at)}
                    </div>
                  </td>
                  <td>
                    <div>{row.interest || row.product_name || '—'}</div>
                    {row.product_name && row.interest && row.product_name !== row.interest ? (
                      <div className="text-xs text-muted-foreground">{row.product_name}</div>
                    ) : null}
                  </td>
                  <td className="max-w-sm whitespace-pre-wrap">{row.message || '—'}</td>
                  <td>
                    <StatusBadge status={row.status} label={STATUS_LABEL[row.status] || row.status} />
                    <div className="mt-1 text-xs text-muted-foreground">{formatDate(row.created_at)}</div>
                  </td>
                  <td>
                    <div className="flex justify-end gap-2">
                      {row.status === 'new' ? (
                        <Button size="sm" variant="outline" onClick={() => setEnquiryStatus(row, 'reviewed')}>
                          Mark reviewed
                        </Button>
                      ) : null}
                      {row.status !== 'closed' ? (
                        <Button size="sm" variant="outline" onClick={() => setEnquiryStatus(row, 'closed')}>
                          Close
                        </Button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </PageShell>
  );
};

export default WebsiteEnquiries;
