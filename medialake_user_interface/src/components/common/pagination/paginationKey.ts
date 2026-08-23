/**
 * Build a stable comparison key from an arbitrary dependency list.
 *
 * Used by the pagination hooks to detect "filters changed, go back to page 1"
 * without requiring callers to pass a fixed-length dependency array.
 */
export const stableKey = (values?: unknown[]): string => {
  if (!values || values.length === 0) return "";
  try {
    return JSON.stringify(values);
  } catch {
    // Non-serializable dependency: fall back to no auto-reset rather than throw.
    return "";
  }
};
