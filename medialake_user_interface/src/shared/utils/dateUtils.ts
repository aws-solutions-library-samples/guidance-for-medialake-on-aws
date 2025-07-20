// src/shared/utils/dateUtils.ts

import {
  format,
  formatDistanceToNow,
  parseISO,
  isValid as isValidDate,
} from "date-fns";
import { enUS } from "date-fns/locale";

interface DateTimeFormatOptions {
  showSeconds?: boolean;
  allowSecondsToggle?: boolean; // unused for now
}

/**
 * Parse a numeric string/number as epoch (auto-multiplies 10-digit by 1000),
 * otherwise parseISO.
 */
const parseDate = (input: string | number): Date => {
  if (typeof input === "number" || /^\d+$/.test(String(input))) {
    const n = Number(input);
    return new Date(String(input).length === 10 ? n * 1000 : n);
  }

  const inputStr = String(input);

  //  If the string doesn't have timezone info, force it to be UTC
  if (
    inputStr.match(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$/) &&
    !inputStr.includes("Z") &&
    !inputStr.includes("+") &&
    !inputStr.includes("-", 10)
  ) {
    // This is a datetime string without timezone info - treat as local time
    return new Date(inputStr + "Z");
  }

  return parseISO(inputStr);
};

/**
 * Returns true if this string is a pure text label (no digits),
 * e.g. "In Progress", "Running".
 */
const isStatusLabel = (input: string | number): input is string =>
  typeof input === "string" && !/\d/.test(input);

/**
 * Format a timestamp/ISO string into something like:
 *   "Jun 18, 2025, 3:45 PM PDT"
 * If you pass a no-digits string, it returns it verbatim.
 * If input is nullish, returns an empty string.
 * Only really bad numbers/ISOs yield "Invalid date".
 */
export const formatLocalDateTime = (
  input?: string | number | null,
  options: DateTimeFormatOptions = {},
): string => {
  if (input == null) {
    return "";
  }

  if (isStatusLabel(input)) {
    return input;
  }

  const date = parseDate(input);
  if (!isValidDate(date)) {
    return "Invalid date";
  }

  const { showSeconds = false } = options;

  // Use Intl.DateTimeFormat for consistent local time formatting
  const formatter = new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    ...(showSeconds && { second: "2-digit" }),
    hour12: true,
    timeZoneName: "short",
  });

  return formatter.format(date);
};

/**
 * "x minutes ago" style. Same passthrough for no-digits labels.
 * Nullish input → empty string.
 */
export const formatRelativeTime = (input?: string | number | null): string => {
  if (input == null) {
    return "";
  }

  if (isStatusLabel(input)) {
    return input;
  }

  const date = parseDate(input);
  if (!isValidDate(date)) {
    return "Invalid date";
  }

  return formatDistanceToNow(date, { addSuffix: true, locale: enUS });
};

/** Quick ISO-validity check */
export const isValidISOString = (input?: string | number | null): boolean => {
  if (input == null || isStatusLabel(input)) {
    return false;
  }
  const date = parseDate(input);
  return isValidDate(date);
};

/** E.g. “PDT” or fallback “America/Los_Angeles” */
export const getTimezoneAbbreviation = (timezone?: string): string => {
  const targetTimezone =
    timezone || Intl.DateTimeFormat().resolvedOptions().timeZone;
  try {
    const parts = new Date()
      .toLocaleTimeString("en-US", {
        timeZone: targetTimezone,
        timeZoneName: "short",
      })
      .split(" ");
    return parts[2] || targetTimezone;
  } catch (error) {
    console.error("Error getting timezone abbreviation:", error);
    return targetTimezone;
  }
};
