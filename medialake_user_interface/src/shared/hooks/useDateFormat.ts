import { useState, useEffect } from "react";
import {
  formatLocalDateTime,
  formatRelativeTime,
  isValidISOString,
} from "../utils/dateUtils";
import { useTimezone } from "../../contexts/TimezoneContext";

interface DateFormatOptions {
  showRelative?: boolean;
  showSeconds?: boolean;
  allowSecondsToggle?: boolean;
  updateInterval?: number;
}

export const useDateFormat = (
  isoString: string | undefined,
  options: DateFormatOptions = {},
) => {
  const {
    showRelative = true,
    showSeconds: initialShowSeconds = false,
    allowSecondsToggle = true,
    updateInterval = 60000,
  } = options;

  // Get timezone from context if available, fallback to browser timezone
  let timezone: string;
  try {
    const timezoneContext = useTimezone();
    timezone = timezoneContext.timezone;
  } catch {
    // If not within TimezoneProvider, use browser timezone
    timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  }

  const [showSeconds, setShowSeconds] = useState(initialShowSeconds);
  const [formattedDate, setFormattedDate] = useState<string>("");

  useEffect(() => {
    if (!isoString || !isValidISOString(isoString)) {
      setFormattedDate("Invalid date");
      return;
    }

    const updateDateTime = () => {
      if (showRelative) {
        setFormattedDate(formatRelativeTime(isoString));
      } else {
        setFormattedDate(formatLocalDateTime(isoString, { showSeconds }));
      }
    };

    updateDateTime();

    if (showRelative) {
      const intervalId = setInterval(updateDateTime, updateInterval);
      return () => clearInterval(intervalId);
    }
  }, [isoString, showRelative, showSeconds, updateInterval, timezone]);

  // Update showSeconds when initialShowSeconds changes
  useEffect(() => {
    setShowSeconds(initialShowSeconds);
  }, [initialShowSeconds]);

  const toggleSeconds = () => {
    if (allowSecondsToggle) {
      setShowSeconds((prev) => !prev);
    }
  };

  return {
    formattedDate,
    absoluteDate: isoString
      ? formatLocalDateTime(isoString, { showSeconds })
      : "Invalid date",
    relativeDate: isoString ? formatRelativeTime(isoString) : "Invalid date",
    showSeconds,
    toggleSeconds,
    canToggleSeconds: allowSecondsToggle,
  };
};
