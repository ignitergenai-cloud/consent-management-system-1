import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from './client';
import type { Incident, PaginatedResponse } from './types';

export interface IncidentListParams {
  page?: number;
  page_size?: number;
  severity?: string;
  status?: string;
  type?: string;
}

export interface ResolveIncidentData {
  resolution_notes?: string;
}

export const incidentsApi = {
  list: async (params?: IncidentListParams): Promise<PaginatedResponse<Incident>> => {
    const response = await apiClient.get<PaginatedResponse<Incident>>(
      '/api/v1/incidents',
      { params },
    );
    return response.data;
  },

  get: async (id: string): Promise<Incident> => {
    const response = await apiClient.get<Incident>(`/api/v1/incidents/${id}`);
    return response.data;
  },

  acknowledge: async (id: string): Promise<Incident> => {
    const response = await apiClient.post<Incident>(
      `/api/v1/incidents/${id}/acknowledge`,
    );
    return response.data;
  },

  resolve: async (id: string, data?: ResolveIncidentData): Promise<Incident> => {
    const response = await apiClient.post<Incident>(
      `/api/v1/incidents/${id}/resolve`,
      data,
    );
    return response.data;
  },
};

export function useIncidents(params?: IncidentListParams) {
  return useQuery({
    queryKey: ['incidents', params],
    queryFn: () => incidentsApi.list(params),
  });
}

export function useIncident(id: string) {
  return useQuery({
    queryKey: ['incidents', id],
    queryFn: () => incidentsApi.get(id),
    enabled: !!id,
  });
}

export function useAcknowledgeIncident() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => incidentsApi.acknowledge(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
    },
  });
}

export function useResolveIncident() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data?: ResolveIncidentData }) =>
      incidentsApi.resolve(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
    },
  });
}
