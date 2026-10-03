import React, { useCallback, useEffect, useState } from 'react';

import { appraisalsAPI } from '../../services/api';
import { toast } from '../../utils/toast';
import { getStoredAuth, hasPermission } from '../../utils/roleAccess';
import { appraisalTone, MONTH_NAMES, starGlyphs } from '../../utils/appraisalStars';
import { cn } from '../../lib/cn';
import { PageShell, PageHeader, PageLoading, EmptyState } from '../page';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/tabs';
import { Card, CardContent } from '../ui/card';
import AppraisalProgressCard from './AppraisalProgressCard';
import AppraisalTemplateForm from './AppraisalTemplateForm';
import AppraisalProgressBar from './AppraisalProgressBar';

export default function AppraisalsPage() {
  const { permissions } = getStoredAuth();
  const canManage = hasPermission(permissions, 'appraisals', 'manage');
  const canTeam = hasPermission(permissions, 'appraisals', 'view_all') || canManage;
  const [me, setMe] = useState(null);
  const [team, setTeam] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const meRes = await appraisalsAPI.me();
      setMe(meRes.data);
      if (canTeam) {
        const teamRes = await appraisalsAPI.team();
        setTeam(teamRes.data?.results || []);
      }
    } catch (error) {
      toast.error(error.response?.data?.error || 'Could not load target delivery');
    } finally {
      setLoading(false);
    }
  }, [canTeam]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSave = async (payload) => {
    setSaving(true);
    try {
      await appraisalsAPI.savePolicy(payload);
      toast.success('Target delivery template saved');
      await load();
    } catch (error) {
      toast.error(error.response?.data?.error || 'Could not save template');
    } finally {
      setSaving(false);
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

  const months = me.year?.months || [];
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
            ? 'Hit your daily closed-sales target. Stars come from collected sales. Use today’s five moves to follow up, talk well, and win more customers.'
            : 'Set daily targets for sales roles and follow the team. Admin accounts are not scored against a personal target.'
        }
      />
      <Tabs defaultValue={defaultTab} className="space-y-4">
        <TabsList>
          {hasPersonalTarget ? <TabsTrigger value="progress">My progress</TabsTrigger> : null}
          {canTeam ? <TabsTrigger value="team">Team</TabsTrigger> : null}
          {canManage ? <TabsTrigger value="template">Template</TabsTrigger> : null}
        </TabsList>

        {hasPersonalTarget ? (
        <TabsContent value="progress" className="space-y-4">
          <AppraisalProgressCard snapshot={me} emphasis />
          {showIncrement ? (
          <Card>
            <CardContent className="space-y-3 p-4">
              <h3 className="text-sm font-semibold">This year</h3>
              <div className="grid grid-cols-3 gap-2 sm:grid-cols-6 lg:grid-cols-12">
                {months.map((row) => {
                  const theme = appraisalTone(row.tone);
                  return (
                    <div
                      key={row.month}
                      className={cn('rounded-md border p-2 text-center', theme.border, theme.bg)}
                    >
                      <p className="text-[11px] uppercase text-muted-foreground">
                        {MONTH_NAMES[row.month - 1]}
                      </p>
                      <p className={cn('text-sm font-semibold', theme.text)}>
                        {Number(row.official_average || 0).toFixed(1)}
                      </p>
                      <p className="text-[11px]">{row.four_star_month ? '4★ month' : '—'}</p>
                    </div>
                  );
                })}
              </div>
              <p className="text-sm text-muted-foreground">{me.policy?.contract_line}</p>
            </CardContent>
          </Card>
          ) : null}
        </TabsContent>
        ) : null}

        {canTeam ? (
          <TabsContent value="team">
            {team.length === 0 ? (
              <EmptyState title="No posted sales yet" description="Team target delivery appears once staff close sales this year." />
            ) : (
              <div className="space-y-3">
                {team.map((row) => {
                  const theme = appraisalTone(row.today?.tone);
                  return (
                    <Card key={row.staff.id} className={cn('border', theme.border)}>
                      <CardContent className="space-y-3 p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div>
                            <p className="font-semibold">{row.staff.name}</p>
                            <p className="text-xs text-muted-foreground">
                              Today {starGlyphs(row.today?.stars)} · Month {Number(row.month?.official_average || 0).toFixed(1)}/5
                            </p>
                          </div>
                          {showIncrement ? (
                          <span className={cn('rounded-full px-2 py-0.5 text-xs font-semibold', theme.pill)}>
                            {row.year?.four_star_months}/{row.year?.four_star_months_required} four-star months
                          </span>
                          ) : null}
                        </div>
                        <AppraisalProgressBar progress={row.month?.progress_to_four_star} tone={row.month?.tone} label="4-star month" />
                        {showIncrement ? (
                          <AppraisalProgressBar progress={row.year?.progress_to_increment} tone={row.year?.tone} label="Year-end increment" />
                        ) : null}
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            )}
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
