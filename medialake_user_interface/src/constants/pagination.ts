/**
 * Pagination constants used across the application
 *
 * These constants provide a single source of truth for pagination behavior,
 * ensuring consistency between frontend and backend components.
 */

/**
 * Default number of items per page
 */
export const DEFAULT_PAGE_SIZE = 50;

/**
 * Maximum allowed page size
 */
export const MAX_PAGE_SIZE = 500;

/**
 * Minimum allowed page size
 */
export const MIN_PAGE_SIZE = 1;

/**
 * Available page size options for user selection
 */
export const PAGE_SIZE_OPTIONS = [10, 25, 50, 100, 200];
