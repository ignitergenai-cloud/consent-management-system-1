import { Chip } from '@mui/material';

const STATUS_COLORS: Record<string, 'success' | 'error' | 'warning' | 'info' | 'default'> = {
  GRANTED: 'success',
  DENIED: 'error',
  PENDING: 'warning',
  SENT: 'info',
  DELIVERED: 'info',
  EXPIRED: 'default',
  REVOKED: 'error',
  FAILED: 'error',
};

export function ConsentStatusChip({ status }: { status: string }) {
  return <Chip label={status} color={STATUS_COLORS[status] || 'default'} size="small" />;
}
