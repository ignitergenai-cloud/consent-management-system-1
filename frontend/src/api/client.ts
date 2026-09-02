import axios from 'axios';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  headers: { 'Content-Type': 'application/json' },
});

function getPageName(pathname: string): string {
  if (pathname === '/' || pathname === '') return 'Dashboard';
  if (pathname.startsWith('/consents/') && pathname.length > 10) return 'ConsentDetail';
  if (pathname.startsWith('/consents')) return 'ConsentsPage';
  if (pathname.startsWith('/analytics')) return 'AnalyticsPage';
  if (pathname.startsWith('/settings')) return 'SettingsPage';
  if (pathname.startsWith('/login')) return 'LoginPage';
  return pathname;
}

function getActionName(method: string, url: string): string {
  const m = (method || 'GET').toUpperCase();
  if (!url) return m;

  if (url.includes('/auth/login'))                               return 'Login';
  if (url.includes('/consents') && url.includes('/revoke'))      return 'RevokeConsent';
  if (url.includes('/consents') && url.includes('/history'))     return 'ViewConsentHistory';
  if (url.includes('/consents/respond'))                         return 'RespondToConsent';
  if (url.includes('/consents/bulk'))                            return 'BulkCreateConsents';
  if (url.includes('/consents') && m === 'POST')                 return 'CreateConsent';
  if (url.includes('/consents') && m === 'PATCH')                return 'UpdateConsent';
  if (url.includes('/consents') && m === 'GET' && url.match(/\/consents\/[^/]+$/)) return 'GetConsent';
  if (url.includes('/consents') && m === 'GET')                  return 'ListConsents';
  if (url.includes('/analytics'))                                return 'ViewAnalytics';
  if (url.includes('/health'))                                   return 'HealthCheck';

  return `${m} ${url}`;
}

// Request interceptor — correlation ID, auth token, UI context headers
apiClient.interceptors.request.use((config) => {
  config.headers['X-Correlation-ID'] = crypto.randomUUID();

  const token = localStorage.getItem('cms_token');
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }

  const pathname = window.location.pathname;
  config.headers['X-UI-Page']   = getPageName(pathname);
  config.headers['X-UI-Action'] = getActionName(config.method ?? 'GET', config.url ?? '');
  config.headers['X-UI-Route']  = pathname;

  return config;
});

// Response interceptor — 401 clears session and redirects to login
apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    const status = (error as { response?: { status?: number } })?.response?.status;
    if (status === 401) {
      localStorage.removeItem('cms_token');
      localStorage.removeItem('cms_user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  },
);

export default apiClient;
