import {
  clearSetupStatusCache,
  markSetupInstalled,
  fetchSetupStatus,
} from './setupStatus';
import { installSessionStorageMock } from '../test-utils';

jest.mock('../services/api', () => ({
  installAPI: {
    status: jest.fn(),
  },
}));

const { installAPI } = require('../services/api');

describe('setupStatus', () => {
  beforeEach(() => {
    installSessionStorageMock();
    clearSetupStatusCache();
    jest.clearAllMocks();
  });

  it('markSetupInstalled caches installed state', () => {
    const data = markSetupInstalled();
    expect(data.installed).toBe(true);
    expect(sessionStorage.getItem('setup_status_cache')).toBeTruthy();
  });

  it('fetchSetupStatus uses cache when fresh', async () => {
    markSetupInstalled();
    const data = await fetchSetupStatus();
    expect(data.installed).toBe(true);
    expect(installAPI.status).not.toHaveBeenCalled();
  });

  it('ignores corrupt cache', async () => {
    sessionStorage.setItem('setup_status_cache', '{bad json');
    installAPI.status.mockResolvedValue({ data: { installed: true } });
    const data = await fetchSetupStatus();
    expect(data.installed).toBe(true);
    expect(installAPI.status).toHaveBeenCalled();
  });

  it('fetchSetupStatus calls API when forced', async () => {
    installAPI.status.mockResolvedValue({ data: { installed: false, needs_install: true } });
    const data = await fetchSetupStatus({ force: true });
    expect(data.needs_install).toBe(true);
    expect(installAPI.status).toHaveBeenCalled();
  });
});
