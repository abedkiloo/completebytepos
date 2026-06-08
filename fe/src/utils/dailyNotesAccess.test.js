import { PERSONA } from './roleAccess';
import {
  managerViewAllDailyNotes,
  salesDailyNotesAccessEnabled,
  salesViewAllDailyNotes,
  userMayViewAllDailyNotes,
} from './dailyNotesAccess';
import { cacheModuleSettings } from './moduleSettingsCache';
import { installLocalStorageMock } from '../test-utils';

const viewAllPerm = [
  { module: 'daily_notes', action: 'view_all', name: 'daily_notes.view_all' },
];

describe('dailyNotesAccess', () => {
  beforeEach(() => {
    installLocalStorageMock();
    localStorage.clear();
  });

  test('sales access follows module flag', () => {
    expect(salesDailyNotesAccessEnabled()).toBe(true);
    expect(salesDailyNotesAccessEnabled({})).toBe(true);
    expect(salesDailyNotesAccessEnabled({ allow_sales_access: false })).toBe(false);
  });

  test('manager and sales view-all settings', () => {
    expect(managerViewAllDailyNotes()).toBe(true);
    expect(managerViewAllDailyNotes({})).toBe(true);
    expect(managerViewAllDailyNotes({ allow_manager_view_all: false })).toBe(false);
    expect(salesViewAllDailyNotes()).toBe(false);
    expect(salesViewAllDailyNotes({})).toBe(false);
    expect(salesViewAllDailyNotes({ allow_sales_view_all: true })).toBe(true);
  });

  test('view_all requires permission', () => {
    expect(userMayViewAllDailyNotes(PERSONA.MANAGER)).toBe(false);
    expect(userMayViewAllDailyNotes(PERSONA.MANAGER, {})).toBe(false);
  });

  test('super admin may view all with permission', () => {
    localStorage.setItem('permissions', JSON.stringify(viewAllPerm));
    expect(userMayViewAllDailyNotes(PERSONA.SUPER_ADMIN, {})).toBe(true);
  });

  test('manager with view_all permission sees all when setting on', () => {
    localStorage.setItem('permissions', JSON.stringify(viewAllPerm));
    expect(userMayViewAllDailyNotes(PERSONA.MANAGER, { allow_manager_view_all: true })).toBe(
      true
    );
    expect(userMayViewAllDailyNotes(PERSONA.MANAGER, { allow_manager_view_all: false })).toBe(
      false
    );
  });

  test('sales view all only when permission and setting enabled', () => {
    localStorage.setItem('permissions', JSON.stringify(viewAllPerm));
    expect(userMayViewAllDailyNotes(PERSONA.SALES, { allow_sales_view_all: true })).toBe(true);
    expect(userMayViewAllDailyNotes(PERSONA.SALES, { allow_sales_view_all: false })).toBe(false);
  });

  test('unknown persona cannot view all', () => {
    localStorage.setItem('permissions', JSON.stringify(viewAllPerm));
    expect(userMayViewAllDailyNotes('guest', {})).toBe(false);
  });
});
