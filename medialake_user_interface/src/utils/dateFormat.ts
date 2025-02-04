import { formatLocalDateTime } from '@/shared/utils/dateUtils';

export function formatDate(dateString: string): string {
    return formatLocalDateTime(dateString, { showSeconds: false });
}

// Export the full date formatting utility for components that need more control
export { formatLocalDateTime } from '@/shared/utils/dateUtils';
