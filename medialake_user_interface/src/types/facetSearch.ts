/**
 * Interface for facet search filters
 */
export interface FacetFilters {
  /**
   * Media type filter
   * Can be a single type or multiple types as comma-separated values (e.g., "Image,Video,Audio")
   */
  type?: string;

  /**
   * File extension filter
   * Can be a single extension or multiple extensions as comma-separated values (e.g., "jpg,png,mp4")
   */
  extension?: string;

  LargerThan?: number;
  asset_size_lte?: number;
  asset_size_gte?: number;
  ingested_date_lte?: string;
  ingested_date_gte?: string;
  filename?: string;

  /**
   * Selected date range option
   * Can be one of: '24h', '7d', '14d', '30d'
   */
  date_range_option?: string;
}

/**
 * Interface for complete search state including query and semantic search
 */
export interface SearchFilters extends FacetFilters {
  /**
   * Search query string
   */
  query?: string;

  /**
   * Whether semantic search is enabled
   */
  isSemantic?: boolean;
}
