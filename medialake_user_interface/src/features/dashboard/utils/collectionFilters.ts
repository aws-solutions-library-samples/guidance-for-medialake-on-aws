import { CollectionViewType, SortConfig } from "../types";

/**
 * Collection interface matching the API response structure
 */
export interface Collection {
  id: string;
  name: string;
  description?: string;
  type: "public" | "private" | "shared";
  parentId?: string;
  collectionTypeId?: string;
  ownerId: string;
  ownerName?: string;
  itemCount: number;
  childCount: number;
  childCollectionCount: number;
  isPublic: boolean;
  status: string;
  userRole?: string;
  createdAt: string;
  updatedAt: string;
  // Sharing metadata
  isShared?: boolean;
  shareCount?: number;
  sharedWithMe?: boolean;
  myRole?: string;
  sharedAt?: string;
  sharedWith?: Array<{
    targetId: string;
    targetType: string;
    role: string;
    grantedAt: string;
  }>;
  ancestors?: Array<{
    id: string;
    name: string;
    parentId?: string;
  }>;
}

/**
 * Filters collections based on the specified view type and current user ID.
 *
 * View Type Logic:
 * - "all": return all collections
 * - "public": filter where isPublic === true
 * - "private": filter where isPublic === false
 * - "my-collections": filter where ownerId === currentUserId
 * - "shared-with-me": collections explicitly shared (use dedicated endpoint, no filtering needed)
 * - "my-shared": collections owned by user that have been shared (use dedicated endpoint, no filtering needed)
 *
 * @param collections - Array of collections to filter
 * @param viewType - The view type determining which collections to display
 * @param currentUserId - The ID of the current user
 * @returns Filtered array of collections based on the view type
 */
export function filterCollections(
  collections: Collection[],
  viewType: CollectionViewType,
  currentUserId: string
): Collection[] {
  switch (viewType) {
    case "all":
      return collections;

    case "public":
      return collections.filter((c) => c.isPublic === true);

    case "private":
      return collections.filter((c) => c.isPublic === false);

    case "my-collections":
      return collections.filter((c) => c.ownerId === currentUserId);

    case "shared-with-me":
    case "my-shared":
      // These use dedicated endpoints, no filtering needed
      return collections;

    default:
      return collections;
  }
}

/**
 * Sorts collections based on the specified sort configuration.
 *
 * Sorting Logic:
 * - sortBy "name": sort alphabetically (case-insensitive)
 * - sortBy "createdAt": sort by creation date
 * - sortBy "updatedAt": sort by update date
 * - sortOrder "asc": ascending order
 * - sortOrder "desc": descending order
 *
 * @param collections - Array of collections to sort
 * @param sortConfig - Configuration specifying sortBy field and sortOrder direction
 * @returns Sorted array of collections (new array, does not mutate input)
 */
export function sortCollections(collections: Collection[], sortConfig: SortConfig): Collection[] {
  const { sortBy, sortOrder } = sortConfig;
  const multiplier = sortOrder === "asc" ? 1 : -1;

  // Create a copy to avoid mutating the input array
  return [...collections].sort((a, b) => {
    let aVal: string | number;
    let bVal: string | number;

    switch (sortBy) {
      case "name":
        // Case-insensitive alphabetical sorting
        aVal = a.name.toLowerCase();
        bVal = b.name.toLowerCase();
        break;
      case "createdAt":
        // Sort by creation date (convert to timestamp for comparison)
        aVal = new Date(a.createdAt).getTime();
        bVal = new Date(b.createdAt).getTime();
        break;
      case "updatedAt":
        // Sort by update date (convert to timestamp for comparison)
        aVal = new Date(a.updatedAt).getTime();
        bVal = new Date(b.updatedAt).getTime();
        break;
    }

    // Compare values and apply sort order multiplier
    if (aVal < bVal) return -1 * multiplier;
    if (aVal > bVal) return 1 * multiplier;
    return 0;
  });
}
