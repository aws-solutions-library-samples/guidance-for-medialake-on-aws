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
}