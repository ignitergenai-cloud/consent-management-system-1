export type ConsentStatus =
  | 'GRANTED'
  | 'DENIED'
  | 'PENDING'
  | 'SENT'
  | 'DELIVERED'
  | 'EXPIRED'
  | 'REVOKED'
  | 'FAILED';

export type ConsentChannel = 'SMS' | 'EMAIL';

export type ConsentType =
  | 'MARKETING'
  | 'DATA_PROCESSING'
  | 'THIRD_PARTY_SHARING'
  | 'COOKIES'
  | 'COMMUNICATIONS';

export interface ConsentRecord {
  consent_id: string;
  customer_id: string;
  consent_type: ConsentType;
  channel: ConsentChannel;
  status: ConsentStatus;
  customer_phone?: string;
  customer_email?: string;
  consent_text: string;
  response_token?: string;
  created_at: string;
  updated_at: string;
  expires_at?: string;
  granted_at?: string;
  denied_at?: string;
  metadata?: Record<string, unknown>;
}

export interface CreateConsentRequest {
  customer_id: string;
  consent_type: ConsentType;
  channel: ConsentChannel;
  customer_phone?: string;
  customer_email?: string;
  consent_text: string;
  expiry_hours?: number;
  metadata?: Record<string, unknown>;
}

export interface CreateConsentResponse {
  id: string;
  status: ConsentStatus;
  message: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  count: number;
  next_token?: string | null;
}

export interface ConsentAnalytics {
  total_consents: number;
  grant_rate: number;
  avg_response_time_hours: number;
  consents_by_status: Record<string, number>;
  consents_by_channel: Record<string, number>;
  daily_counts: Array<{
    date: string;
    granted: number;
    denied: number;
  }>;
}

export interface NotificationLog {
  id: string;
  consent_id: string;
  channel: ConsentChannel;
  status: string;
  sent_at: string;
  delivered_at?: string;
  error_message?: string;
}

export interface HealthStatus {
  status: string;
  version: string;
  uptime_seconds: number;
  checks: Record<
    string,
    {
      status: string;
      latency_ms: number;
    }
  >;
}

export interface ConsentHistoryEntry {
  id: string;
  consent_id: string;
  previous_status: ConsentStatus;
  new_status: ConsentStatus;
  changed_at: string;
  changed_by?: string;
  reason?: string;
}
