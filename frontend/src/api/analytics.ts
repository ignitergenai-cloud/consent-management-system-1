import { useQuery } from '@tanstack/react-query';
import apiClient from './client';
import type { ConsentAnalytics, HealthStatus } from './types';

export interface AnalyticsParams {
  start_date?: string;
  end_date?: string;
  channel?: string;
  consent_type?: string;
}

export const analyticsApi = {
  getConsentAnalytics: async (params?: AnalyticsParams): Promise<ConsentAnalytics> => {
    const response = await apiClient.get<ConsentAnalytics>(
      '/api/v1/analytics/consents',
      { params },
    );
    return response.data;
  },

  getHealth: async (): Promise<HealthStatus> => {
    const response = await apiClient.get<HealthStatus>('/api/v1/health');
    return response.data;
  },
};

export function useConsentAnalytics(params?: AnalyticsParams) {
  return useQuery({
    queryKey: ['analytics', 'consents', params],
    queryFn: () => analyticsApi.getConsentAnalytics(params),
  });
}

export function useHealthStatus() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => analyticsApi.getHealth(),
    refetchInterval: 60000,
  });
}
