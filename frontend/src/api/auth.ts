import apiClient from './client';

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: { username: string; name: string; role: string };
}

export const authApi = {
  login: async (username: string, password: string): Promise<LoginResponse> => {
    const response = await apiClient.post<LoginResponse>('/api/v1/auth/login', { username, password });
    return response.data;
  },
};
