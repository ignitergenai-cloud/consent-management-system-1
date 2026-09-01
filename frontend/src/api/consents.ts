import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from './client';
import type {
  ConsentRecord,
  CreateConsentRequest,
  CreateConsentResponse,
  PaginatedResponse,
  ConsentHistoryEntry,
} from './types';

export interface ConsentListParams {
  page?: number;
  page_size?: number;
  status?: string;
  channel?: string;
  customer_id?: string;
  start_date?: string;
  end_date?: string;
}

export const consentsApi = {
  list: async (params?: ConsentListParams): Promise<PaginatedResponse<ConsentRecord>> => {
    const response = await apiClient.get<PaginatedResponse<ConsentRecord>>(
      '/api/v1/consents',
      { params },
    );
    return response.data;
  },

  get: async (id: string): Promise<ConsentRecord> => {
    const response = await apiClient.get<ConsentRecord>(`/api/v1/consents/${id}`);
    return response.data;
  },

  create: async (data: CreateConsentRequest): Promise<CreateConsentResponse> => {
    const response = await apiClient.post<CreateConsentResponse>('/api/v1/consents', data);
    return response.data;
  },

  update: async (id: string, data: Partial<ConsentRecord>): Promise<ConsentRecord> => {
    const response = await apiClient.patch<ConsentRecord>(`/api/v1/consents/${id}`, data);
    return response.data;
  },

  revoke: async (id: string): Promise<ConsentRecord> => {
    const response = await apiClient.post<ConsentRecord>(`/api/v1/consents/${id}/revoke`);
    return response.data;
  },

  bulkCreate: async (data: CreateConsentRequest[]): Promise<CreateConsentResponse[]> => {
    const response = await apiClient.post<CreateConsentResponse[]>(
      '/api/v1/consents/bulk',
      data,
    );
    return response.data;
  },

  getHistory: async (id: string): Promise<ConsentHistoryEntry[]> => {
    const response = await apiClient.get<ConsentHistoryEntry[]>(
      `/api/v1/consents/${id}/history`,
    );
    return response.data;
  },
};

export function useConsents(params?: ConsentListParams) {
  return useQuery({
    queryKey: ['consents', params],
    queryFn: () => consentsApi.list(params),
  });
}

export function useConsent(id: string) {
  return useQuery({
    queryKey: ['consents', id],
    queryFn: () => consentsApi.get(id),
    enabled: !!id,
  });
}

export function useCreateConsent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateConsentRequest) => consentsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['consents'] });
    },
  });
}

export function useRevokeConsent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => consentsApi.revoke(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['consents'] });
    },
  });
}

export function useConsentHistory(id: string) {
  return useQuery({
    queryKey: ['consents', id, 'history'],
    queryFn: () => consentsApi.getHistory(id),
    enabled: !!id,
  });
}
