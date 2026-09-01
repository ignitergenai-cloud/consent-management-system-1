import type { ConsentChannel, ConsentStatus, ConsentType } from '../api/types';

export const CONSENT_STATUSES: ConsentStatus[] = [
  'GRANTED',
  'DENIED',
  'PENDING',
  'SENT',
  'DELIVERED',
  'EXPIRED',
  'REVOKED',
  'FAILED',
];

export const CONSENT_CHANNELS: ConsentChannel[] = ['SMS', 'EMAIL'];

export const CONSENT_TYPES: ConsentType[] = [
  'MARKETING',
  'DATA_PROCESSING',
  'THIRD_PARTY_SHARING',
  'COOKIES',
  'COMMUNICATIONS',
];

export const CONSENT_STATUS_COLORS: Record<ConsentStatus, string> = {
  GRANTED: '#4caf50',
  DENIED: '#f44336',
  PENDING: '#ff9800',
  SENT: '#2196f3',
  DELIVERED: '#00bcd4',
  EXPIRED: '#9e9e9e',
  REVOKED: '#e91e63',
  FAILED: '#d32f2f',
};
