import { format, formatDistanceToNow, parseISO } from 'date-fns';
import { enUS } from 'date-fns/locale';

interface DateTimeFormatOptions {
  showSeconds?: boolean;
  allowSecondsToggle?: boolean;
}

export const formatLocalDateTime = (isoString: string, options: DateTimeFormatOptions = {}): string => {
  try {
    const { showSeconds = false } = options;
    // Parse the UTC date string
    const utcDate = parseISO(isoString);
    
    // Convert to local time
    const localDate = new Date(utcDate.getTime() - (utcDate.getTimezoneOffset() * 60000));
    
    // Format the date in local time with timezone indicator
    // PP = date format (e.g., Apr 29, 2023)
    // p = time without seconds (e.g., 12:00 PM)
    // pp = time with seconds (e.g., 12:00:00 PM)
    const formatString = `PP, ${showSeconds ? 'pp' : 'p'}`;
    return format(localDate, formatString, { locale: enUS }) + ' ' + getTimezoneAbbreviation();
  } catch (error) {
    console.error('Error formatting date:', error);
    return 'Invalid date';
  }
};

export const formatRelativeTime = (isoString: string): string => {
  try {
    // Parse the UTC date
    const utcDate = parseISO(isoString);
    
    // Convert to local time
    const localDate = new Date(utcDate.getTime() - (utcDate.getTimezoneOffset() * 60000));
    
    return formatDistanceToNow(localDate, { 
      addSuffix: true,
      locale: enUS
    });
  } catch (error) {
    console.error('Error formatting relative time:', error);
    return 'Invalid date';
  }
};

export const isValidISOString = (isoString: string): boolean => {
  try {
    return !isNaN(Date.parse(isoString));
  } catch {
    return false;
  }
};

// Helper function to get timezone abbreviation
export const getTimezoneAbbreviation = (): string => {
  return new Date()
    .toLocaleTimeString('en-US', { timeZoneName: 'short' })
    .split(' ')[2] || 
    Intl.DateTimeFormat().resolvedOptions().timeZone;
}; 
