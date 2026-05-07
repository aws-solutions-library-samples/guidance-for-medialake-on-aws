import { formatLocalDateTime } from "@/shared/utils/dateUtils";

export function formatDate(dateString: string | number | null | undefined): string {
  if (!dateString) {
    return "";
  }
  return formatLocalDateTime(dateString, { showSeconds: false });
}

/**
 * Format a date string to show only the date portion (e.g. "Jun 18, 2025")
 * without time or timezone information.
 */
export function formatDateOnly(dateString: string | number | null | undefined): string {
  if (!dateString) {
    return "";
  }
  try {
    const date = new Date(
      typeof dateString === "number" || /^\d+$/.test(String(dateString))
        ? String(dateString).length === 10
          ? Number(dateString) * 1000
          : Number(dateString)
        : dateString
    );
    if (isNaN(date.getTime())) return "";
    return new Intl.DateTimeFormat("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    }).format(date);
  } catch {
    return "";
  }
}

// Export the full date formatting utility for components that need more control
export {
  formatLocalDateTime,
  formatRelativeTime,
  isValidISOString,
} from "@/shared/utils/dateUtils";
