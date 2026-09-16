jest.mock('../../services/api', () => ({
  modulesAPI: {},
  storeSettingsAPI: {},
}));

import { NAV_SECTIONS } from './Layout';
import { ROUTE_MODULE_MAP } from '../../utils/permissionRoutes';

describe('navigation permission contract', () => {
  test('every business navigation item has an explicit permission', () => {
    const missing = NAV_SECTIONS.flatMap((section) =>
      section.items
        .filter((item) => item.to !== '/' && !item.permission)
        .map((item) => `${section.id}:${item.to}`)
    );

    expect(missing).toEqual([]);
  });

  test('every business route is registered for route authorization', () => {
    const registeredPrefixes = Object.keys(ROUTE_MODULE_MAP);
    const missing = NAV_SECTIONS.flatMap((section) =>
      section.items
        .map((item) => item.to.split('?')[0])
        .filter((path) => path !== '/')
        .filter(
          (path) =>
            !registeredPrefixes.some(
              (prefix) => path === prefix || path.startsWith(`${prefix}/`)
            )
        )
    );

    expect(missing).toEqual([]);
  });
});
