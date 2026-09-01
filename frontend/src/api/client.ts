import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  headers: { 'Content-Type': 'application/json' },
});

// Map URL path → human-readable page name
function getPageName(pathname: string): string {
  if (pathname === '/' || pathname === '') return 'Dashboard';
  if (pathname.startsWith('/consents/') && pathname.length > 10) return 'ConsentDetail';
  if (pathname.startsWith('/consents')) return 'ConsentsPage';
  if (pathname.startsWith('/incidents/') && pathname.length > 11) return 'IncidentDetail';
  if (pathname.startsWith('/incidents')) return 'IncidentsPage';
  if (pathname.startsWith('/analytics')) return 'AnalyticsPage';
  if (pathname.startsWith('/settings')) return 'SettingsPage';
  if (pathname.startsWith('/customers')) return 'CustomersPage';
  return pathname;
}

// Map HTTP method + API path → human-readable action
function getActionName(method: string, url: string): string {
  const m = (method || 'GET').toUpperCase();
  if (!url) return m;

  if (url.includes('/consents') && url.includes('/revoke'))  return 'RevokeConsent';
  if (url.includes('/consents') && url.includes('/history')) return 'ViewConsentHistory';
  if (url.includes('/consents/respond'))                     return 'RespondToConsent';
  if (url.includes('/consents/bulk'))                        return 'BulkCreateConsents';
  if (url.includes('/consents') && m === 'POST')             return 'CreateConsent';
  if (url.includes('/consents') && m === 'PATCH')            return 'UpdateConsent';
  if (url.includes('/consents') && m === 'GET' && url.match(/\/consents\/[^/]+$/)) return 'GetConsent';
  if (url.includes('/consents') && m === 'GET')              return 'ListConsents';

  if (url.includes('/incidents') && url.includes('/acknowledge')) return 'AcknowledgeIncident';
  if (url.includes('/incidents') && url.includes('/resolve'))     return 'ResolveIncident';
  if (url.includes('/incidents') && m === 'GET' && url.match(/\/incidents\/[^/]+$/)) return 'GetIncident';
  if (url.includes('/incidents') && m === 'GET')                  return 'ListIncidents';

  if (url.includes('/analytics')) return 'ViewAnalytics';
  if (url.includes('/health'))    return 'HealthCheck';
  if (url.includes('/customers')) return 'ListCustomerConsents';

  return `${m} ${url}`;
}

apiClient.interceptors.request.use((config) => {
  config.headers['X-Correlation-ID'] = crypto.randomUUID();

  const pathname = window.location.pathname;
  const page = getPageName(pathname);
  const action = getActionName(config.method ?? 'GET', config.url ?? '');

  config.headers['X-UI-Page'] = page;
  config.headers['X-UI-Action'] = action;
  config.headers['X-UI-Route'] = pathname;

  return config;
});

export default apiClient;
