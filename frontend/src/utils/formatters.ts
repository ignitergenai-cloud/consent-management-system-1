import { format, formatDistanceToNow, parseISO } from 'date-fns';

/**
 * Format a date string to a short readable format (e.g. "Jan 15, 2025").
 */
export function formatDate(dateString: string): string {
  try {
    const date = parseISO(dateString);
    return format(date, 'MMM d, yyyy');
  } catch {
    return dateString;
  }
}

/**
 * Format a date string to include date and time (e.g. "Jan 15, 2025, 2:30 PM").
 */
export function formatDateTime(dateString: string): string {
  try {
    const date = parseISO(dateString);
    return format(date, 'MMM d, yyyy, h:mm a');
  } catch {
    return dateString;
  }
}

/**
 * Format a decimal number as a percentage string (e.g. 0.856 -> "85.6%").
 */
export function formatPercentage(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

/**
 * Format a duration in hours to a human-readable string.
 * For durations less than 1 hour, shows minutes.
 * For durations >= 24 hours, shows days and hours.
 */
export function formatDuration(hours: number): string {
  if (hours < 1) {
    const minutes = Math.round(hours * 60);
    return `${minutes}m`;
  }
  if (hours < 24) {
    return `${hours.toFixed(1)}h`;
  }
  const days = Math.floor(hours / 24);
  const remainingHours = Math.round(hours % 24);
  return remainingHours > 0 ? `${days}d ${remainingHours}h` : `${days}d`;
}

/**
 * Truncate a UUID or long ID for display (e.g. "a1b2c3d4-..." -> "a1b2c3d4").
 */
export function truncateId(id: string | undefined | null, length: number = 8): string {
  if (!id) return '—';
  if (id.length <= length) {
    return id;
  }
  return `${id.substring(0, length)}…`;
}

/**
 * Format a date string as a relative time (e.g. "3 hours ago").
 */
export function formatRelativeTime(dateString: string): string {
  try {
    const date = parseISO(dateString);
    return formatDistanceToNow(date, { addSuffix: true });
  } catch {
    return dateString;
  }
}
