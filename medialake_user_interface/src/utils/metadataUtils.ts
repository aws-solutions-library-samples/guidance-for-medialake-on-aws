/**
 * Utility functions for transforming metadata into accordion format
 * Used across multiple detail pages and public share pages
 */

/**
 * Transform flat metadata object into hierarchical accordion structure
 * Expected metadata structure: { ParentCategory: { SubCategory: data } }
 */
export const transformMetadata = (metadata: any) => {
  console.log("Transforming metadata:", metadata);
  if (!metadata) return [];

  return Object.entries(metadata).map(([parentCategory, parentData]) => ({
    category: parentCategory,
    subCategories: Object.entries(parentData as object).map(([subCategory, data]) => ({
      category: subCategory,
      data: data,
      count:
        typeof data === "object"
          ? Array.isArray(data)
            ? data.length
            : Object.keys(data).length
          : 1,
    })),
    count: Object.keys(parentData as object).length,
  }));
};
