import {
  callBookCountLine,
  callCoveragePercent,
  callDayPlanCounts,
  callDayPlanTicker,
  callerChangedLine,
  callerNamesLine,
  customerCategoryLabel,
  dayClaimBlockedLine,
  outcomeLabel,
  daySubCountyLabel,
  weekdayLabel,
} from './callBook';

describe('call book labels', () => {
  test('weekdays are Monday to Friday only', () => {
    expect(weekdayLabel(0)).toBe('Monday');
    expect(weekdayLabel(4)).toBe('Friday');
    expect(weekdayLabel(5)).toBe('');
    expect(weekdayLabel(6)).toBe('');
  });

  test('ask later stays a visible outcome', () => {
    expect(outcomeLabel('ask_later')).toBe('Call later');
    expect(outcomeLabel('unreachable')).toBe('Unreachable');
    expect(outcomeLabel('called')).toBe('Called');
    expect(outcomeLabel('no_answer')).toBe('No answer');
  });

  test('the count line covers called, callable, and cannot-call', () => {
    expect(callBookCountLine({
      called: 2,
      callable: 5,
      cannot_call: 1,
    })).toBe('Called 2 of 5. 1 cannot be called.');
    expect(callBookCountLine(null)).toBe('');
  });

  test('unit: day plan counts and ticker follow the selected weekday', () => {
    const summary = {
      days: [
        { weekday: 0, callable: 5, called: 2, not_called: 3 },
        { weekday: 2, callable: 1, called: 0, not_called: 1 },
      ],
    };
    expect(callDayPlanCounts(summary, 0)).toEqual({
      weekday: 0,
      called: 2,
      not_called: 3,
      callable: 5,
    });
    expect(callDayPlanCounts(summary, 1)).toEqual({
      weekday: 1,
      called: 0,
      not_called: 0,
      callable: 0,
    });
    expect(callDayPlanTicker(callDayPlanCounts(summary, 0))).toBe('2 called · 3 not called');
    expect(callDayPlanTicker(callDayPlanCounts(summary, 0), { includeCallable: true }))
      .toBe('2 called · 3 not called · 5 on plan');
  });

  test('corrected: ticker never embeds a phone number', () => {
    const line = callDayPlanTicker({
      called: 1,
      not_called: 4,
      callable: 5,
      phone: '0718000999',
    }, { includeCallable: true });
    expect(line).toBe('1 called · 4 not called · 5 on plan');
    expect(line).not.toMatch(/07\d|phone/i);
  });

  test('security: missing summary or bad weekday yields no ticker text', () => {
    expect(callDayPlanCounts(null, 0)).toBeNull();
    expect(callDayPlanCounts({}, 9)).toBeNull();
    expect(callDayPlanTicker(null)).toBe('');
  });

  test('stress: day ticker stays stable across many day rows', () => {
    const days = Array.from({ length: 300 }, (_, i) => ({
      weekday: i % 5,
      callable: i + 1,
      called: i,
      not_called: 1,
    }));
    for (let i = 0; i < 300; i += 1) {
      expect(callDayPlanTicker(days[i])).toBe(`${i} called · 1 not called`);
    }
  });

  test('a day header names its sub-counties once', () => {
    expect(daySubCountyLabel({ sub_counties: ['Starehe', 'Westlands'] })).toBe('Starehe, Westlands');
    expect(daySubCountyLabel({
      sub_counties: ['A', 'B', 'C', 'D', 'E'],
    }, 2)).toBe('A, B +3 more');
    expect(daySubCountyLabel({})).toBe('');
  });

  test('coverage is a whole percent and categories stay short', () => {
    expect(callCoveragePercent(1, 2)).toBe(50);
    expect(callCoveragePercent(0, 0)).toBe(0);
    expect(customerCategoryLabel('at_risk')).toBe('Cooling off');
    expect(customerCategoryLabel('active')).toBe('Existing customer');
  });

  test('unit: caller names and day-claim lines stay phone-free', () => {
    expect(callerNamesLine([
      { called_by: 'Ada' },
      { called_by: 'Ada' },
      { called_by: 'Ben' },
    ])).toBe('Ada, Ben');
    expect(callerChangedLine({
      caller_changed: true,
      callers_this_week: [{ called_by: 'Ada' }],
      callers_last_week: [{ called_by: 'Ben' }],
    })).toContain('This week: Ada');
    expect(dayClaimBlockedLine({ held_by: 'Mercy', held_by_me: false }))
      .toContain('Mercy claimed this customer for today');
    expect(dayClaimBlockedLine({ held_by_me: true })).toBe('');
  });

  test('security: caller helpers never echo a phone number', () => {
    const line = callerNamesLine([
      { called_by: 'Ada', phone: '0718000999' },
      { called_by: '0718000888' },
    ]);
    expect(line).toBe('Ada, 0718000888');
    expect(dayClaimBlockedLine({
      held_by: 'Mercy',
      held_by_me: false,
      phone: '0718000777',
    })).not.toMatch(/0718000777/);
  });
});
