import {
  EXPORT_FORMATS,
  REPORT_EXPORT_PATHS,
  downloadReportExport,
  normalizeReportExportFormat,
  reportExportFilename,
  reportExportPath,
  reportExportQuery,
  salesHistoryExportParams,
  reportExportRequestPath,
} from './reportExport';

describe('reportExport', () => {
  beforeEach(() => {
    const click = jest.fn();
    const anchor = { click, href: '', download: '' };
    jest.spyOn(document, 'createElement').mockReturnValue(anchor);
    Object.defineProperty(document.body, 'appendChild', { value: jest.fn(), configurable: true });
    Object.defineProperty(document.body, 'removeChild', { value: jest.fn(), configurable: true });
    window.URL.createObjectURL = jest.fn(() => 'blob:export');
    window.URL.revokeObjectURL = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('maps report slugs to API paths', () => {
    expect(reportExportPath('sales')).toBe('/reports/sales/');
    expect(reportExportPath('profit-loss')).toBe('/reports/profit_loss/');
    expect(reportExportPath('sales-by-person')).toBe('/reports/sales_by_person/');
    expect(reportExportPath('sales-history')).toBe('/sales/export/');
    expect(reportExportPath('unknown')).toBeNull();
    expect(Object.keys(REPORT_EXPORT_PATHS).length).toBeGreaterThan(10);
  });

  it('normalizes format aliases', () => {
    expect(normalizeReportExportFormat('Excel')).toBe('xlsx');
    expect(normalizeReportExportFormat('xls')).toBe('xlsx');
    expect(normalizeReportExportFormat('PDF')).toBe('pdf');
    expect(normalizeReportExportFormat('csv')).toBe('csv');
    expect(normalizeReportExportFormat('')).toBeNull();
    expect(normalizeReportExportFormat('ppt')).toBeNull();
  });

  it('builds dated filenames', () => {
    const when = new Date('2026-08-17T10:00:00.000Z');
    expect(reportExportFilename('sales', 'pdf', when)).toBe('sales_2026-08-17.pdf');
    expect(reportExportFilename('sales', 'excel', when)).toBe('sales_2026-08-17.xlsx');
    expect(reportExportFilename('', 'csv', when)).toBe('report_2026-08-17.csv');
  });

  it('omits empty query params and adds format', () => {
    expect(reportExportQuery({ date_from: '2026-08-01', date_to: '', period: 'month' }, 'xlsx')).toEqual(
      { date_from: '2026-08-01', period: 'month', format: 'xlsx' }
    );
  });

  it('builds request path with query string', () => {
    expect(reportExportRequestPath('sales', { period: 'month' }, 'pdf')).toBe(
      '/reports/sales/?period=month&format=pdf'
    );
    expect(reportExportRequestPath('missing', {}, 'pdf')).toBeNull();
  });

  it('downloads via authenticated client', async () => {
    const get = jest.fn().mockResolvedValue({
      data: new Blob(['%PDF-1.4'], { type: 'application/pdf' }),
      headers: { 'content-type': 'application/pdf' },
    });
    const filename = await downloadReportExport(
      { get },
      { slug: 'sales', params: { period: 'month' }, format: 'pdf' }
    );
    expect(filename).toMatch(/sales_.*\.pdf/);
    expect(get).toHaveBeenCalled();
    const [path] = get.mock.calls[0];
    expect(path).toContain('/reports/sales/');
    expect(path).toContain('format=pdf');
  });

  it('rejects unknown report and format', async () => {
    await expect(
      downloadReportExport({ get: jest.fn() }, { slug: 'nope', format: 'pdf' })
    ).rejects.toThrow(/cannot be exported/i);
    await expect(
      downloadReportExport({ get: jest.fn() }, { slug: 'sales', format: 'ppt' })
    ).rejects.toThrow(/Choose PDF/i);
  });

  it('omits format when none is provided', () => {
    expect(reportExportQuery({ period: 'month' })).toEqual({ period: 'month' });
    expect(reportExportRequestPath('inventory', {}, 'pdf')).toBe(
      '/reports/inventory/?format=pdf'
    );
  });

  it('defaults filename, query, and path when format is missing', () => {
    const when = new Date('2026-08-17T10:00:00.000Z');
    expect(reportExportFilename('sales', null, when)).toBe('sales_2026-08-17.pdf');
    expect(reportExportQuery()).toEqual({});
    expect(reportExportQuery({ period: null, date_from: '2026-08-01' })).toEqual({
      date_from: '2026-08-01',
    });
    expect(reportExportRequestPath('sales')).toBe('/reports/sales/?format=pdf');
    expect(reportExportRequestPath('sales', {}, '')).toBe('/reports/sales/');
  });

  it('defaults download format to pdf', async () => {
    const get = jest.fn().mockResolvedValue({
      data: new Blob(['%PDF-1.4'], { type: 'application/pdf' }),
      headers: { 'content-type': 'application/pdf' },
    });
    await downloadReportExport({ get }, { slug: 'sales' });
    expect(get.mock.calls[0][0]).toContain('format=pdf');
  });

  it('exposes the three download formats', () => {
    expect(EXPORT_FORMATS.map((row) => row.id)).toEqual(['pdf', 'xlsx', 'csv']);
  });

  it('builds sales-history export params from list filters', () => {
    expect(
      salesHistoryExportParams({
        date_from: '2026-08-01',
        date_to: '',
        payment_method: 'cash',
        search: '  ',
      })
    ).toEqual({ date_from: '2026-08-01', payment_method: 'cash', search: '  ' });
    expect(salesHistoryExportParams()).toEqual({});
  });
});
