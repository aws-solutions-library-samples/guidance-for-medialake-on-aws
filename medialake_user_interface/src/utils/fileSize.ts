/**
 * Format a file size in bytes to a human-readable string
 * @param sizeInBytes The file size in bytes
 * @returns A formatted string (e.g., "1.5 MB")
 */
export const formatFileSize = (sizeInBytes: number): string => {
  if (sizeInBytes === 0) return '0 B';
  
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
  const i = Math.floor(Math.log(sizeInBytes) / Math.log(1024));
  
  // Handle edge case for very large files
  if (i >= sizes.length) {
    return 'File too large';
  }
  
  return `${(sizeInBytes / Math.pow(1024, i)).toFixed(2)} ${sizes[i]}`;
};
