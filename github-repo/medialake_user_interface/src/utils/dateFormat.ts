import { formatLocalDateTime } from "@/shared/utils/dateUtils";

export function formatDate(
  dateString: string | number | null | undefined,
): string {
  if (!dateString) {
    return "";
  }
  return formatLocalDateTime(dateString, { showSeconds: false });
}

// Export the full date formatting utility for components that need more control
export {
  formatLocalDateTime,
  formatRelativeTime,
  isValidISOString,
} from "@/shared/utils/dateUtils";
