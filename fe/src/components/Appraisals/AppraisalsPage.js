import React, { useCallback, useEffect, useState } from 'react';

import { appraisalsAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { getStoredAuth, hasPermission } from '../../utils/roleAccess';
import { canViewDailySalesFromStorage, dailySalesListPath } from '../../utils/dailySalesAccess';
import { PageShell, PageHeader, PageLoading, EmptyState } from '../page';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { Button } from '../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import AppraisalDashboard from './AppraisalDashboard';
import AppraisalTemplateForm from './AppraisalTemplateForm';
import AppraisalTeamBoard from './AppraisalTeamBoard';

export default function AppraisalsPage() {
  const { permissions } = getStoredAuth();
  const canManage = hasPermission(permissions, 'appraisals', 'manage');
  const canTeam = hasPermission(permissions, 'appraisals', 'view_all') || canManage;
  const [me, setMe] = useState(null);
  const [team, setTeam] = useState({ results: [], insights: null });
  const [increments, setIncrements] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const meRes = await appraisalsAPI.me();
      setMe(meRes.data);
      if (canTeam) {
        const teamRes = await appraisalsAPI.team();
        setTeam(teamRes.data || { results: [], insights: null });
      }
      if (canManage && appraisalsAPI.increments) {
        try {
          const incRes = await appraisalsAPI.increments();
          setIncrements(incRes.data?.results || []);
        } catch (_err) {
          setIncrements([]);
        }
      }
    } catch (error) {
      toast.error(error.response?.data?.error || 'Could not load target delivery');
    } finally {
      setLoading(false);
    }
  }, [canTeam, canManage]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSave = async (payload) => {
    setSaving(true);
    try {
      await appraisalsAPI.savePolicy(payload);
      toast.success('Performance rules saved');
      await load();
    } catch (error) {
      toast.error(error.response?.data?.error || 'Could not save template');
    } finally {
      setSaving(false);
    }
  };

  const handleIncrement = async (id, decision) => {
    try {
      await appraisalsAPI.decideIncrement(id, { decision });
      toast.success(decision === 'reject' ? 'Increment rejected' : 'Increment approved');
      await load();
    } catch (error) {
      toast.error(error.response?.data?.error || 'Could not update increment');
    }
  };

  if (loading) {
    return (
      <PageShell>
        <PageLoading rows={4} />
      </PageShell>
    );
  }

  if (!me) {
    return (
      <PageShell>
        <EmptyState title="Target delivery unavailable" description="Your account cannot load target delivery yet." />
      </PageShell>
    );
  }

  const showIncrement = Boolean(me.policy?.show_year_end_increment);
  const hasPersonalTarget = me.has_personal_target !== false;
  const defaultTab = hasPersonalTarget
    ? 'progress'
    : canTeam
      ? 'team'
      : canManage
        ? 'template'
        : 'progress';

  return (
    <PageShell>
      <PageHeader
        eyebrow="People"
        title="Target delivery"
        description={
          hasPersonalTarget
            ? 'See today’s target, your stars, monthly bonus, and salary growth in one place. Stars come from collected sales.'
            : 'Set daily targets for sales roles and follow the team. Admin accounts are not scored against a personal target.'
        }
      />
      <Tabs defaultValue={defaultTab} className="space-y-4">
        <TabsList>
          {hasPersonalTarget ? <TabsTrigger value="progress">My progress</TabsTrigger> : null}
          {canTeam ? <TabsTrigger value="team">Team</TabsTrigger> : null}
          {canManage ? <TabsTrigger value="template">Performance rules</TabsTrigger> : null}
        </TabsList>

        {hasPersonalTarget ? (
        <TabsContent value="progress" className="space-y-4">
          <AppraisalDashboard
            snapshot={me}
            dayHref={canViewDailySalesFromStorage() ? dailySalesListPath : undefined}
          />
        </TabsContent>
        ) : null}

        {canTeam ? (
          <TabsContent value="team" className="space-y-4">
            <AppraisalTeamBoard team={team} showIncrement={showIncrement} />
            {canManage && increments.length ? (
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Annual increments</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {increments.map((row) => (
                    <div key={row.id || `${row.user_id}-${row.year}`} className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3 text-sm">
                      <div>
                        <p className="font-medium">{row.role_name || 'Staff'} · {row.year}</p>
                        <p className="text-muted-foreground">
                          {row.status} · KES {Math.round(row.previous_basic || 0).toLocaleString('en-KE')}
                          {' → '}
                          KES {Math.round(row.new_basic || 0).toLocaleString('en-KE')}
                        </p>
                      </div>
                      {row.status === 'pending' && row.id ? (
                        <div className="flex gap-2">
                          <Button type="button" size="sm" onClick={() => handleIncrement(row.id, 'approve')}>Approve</Button>
                          <Button type="button" size="sm" variant="outline" onClick={() => handleIncrement(row.id, 'reject')}>Reject</Button>
                        </div>
                      ) : null}
                    </div>
                  ))}
                </CardContent>
              </Card>
            ) : null}
          </TabsContent>
        ) : null}

        {canManage && me.policy ? (
          <TabsContent value="template">
            <AppraisalTemplateForm policy={me.policy} saving={saving} onSave={handleSave} />
          </TabsContent>
        ) : null}
      </Tabs>
    </PageShell>
  );
}
