import { format, formatDistanceToNow, parseISO } from 'date-fns';
import { enUS } from 'date-fns/locale';

interface DateTimeFormatOptions {
  showSeconds?: boolean;
  allowSecondsToggle?: boolean;
}

const convertToDate = (input: string | number): Date => {
  try {
    // If it's a number or string number, treat as epoch timestamp
    if (!isNaN(Number(input))) {
      const ms = String(input).length === 10 ? Number(input) * 1000 : Number(input);
      return new Date(ms);
    }
    // Otherwise try to parse as ISO string
    return parseISO(String(input));
  } catch (error) {
    console.error('Error converting to date:', error);
    throw new Error('Invalid date input');
  }
};

export const formatLocalDateTime = (input: string | number, options: DateTimeFormatOptions = {}): string => {
  try {
    const { showSeconds = false } = options;
    const date = convertToDate(input);
    
    // Format the date in local time with timezone indicator
    const formatString = `PP, ${showSeconds ? 'pp' : 'p'}`;
    return format(date, formatString, { locale: enUS }) + ' ' + getTimezoneAbbreviation();
  } catch (error) {
    console.error('Error formatting date:', error);
    return 'Invalid date';
  }
};

export const formatRelativeTime = (input: string | number): string => {
  try {
    const date = convertToDate(input);
    return formatDistanceToNow(date, { 
      addSuffix: true,
      locale: enUS
    });
  } catch (error) {
    console.error('Error formatting relative time:', error);
    return 'Invalid date';
  }
};

export const isValidISOString = (input: string | number): boolean => {
  try {
    convertToDate(input);
    return true;
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
