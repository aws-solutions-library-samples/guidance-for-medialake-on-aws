export const formatDateTime = (isoString: string): string => {
  try {
    const date = new Date(isoString);
    return date.toLocaleString();
  } catch (e) {
    console.error('Invalid date format:', e);
    return isoString;
  }
};

export const getUnixTimestamp = (date: Date): number => {
  return Math.floor(date.getTime() / 1000);
};

export const fromUnixTimestamp = (timestamp: number): Date => {
  return new Date(timestamp * 1000);
}; 