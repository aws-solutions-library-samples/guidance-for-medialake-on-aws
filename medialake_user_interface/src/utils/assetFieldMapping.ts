/**
 * Static field mapping between API field IDs and card field IDs.
 * Extracted from AssetCard to avoid recreating on every render.
 */
import { type AssetField } from "@/types/shared/assetComponents";
export type { AssetField };

export const FIELD_MAPPING: Record<string, string> = {
  // Root level fields (new API structure)
  id: "id",
  assetType: "type",
  format: "format",
  createdAt: "createdAt",
  objectName: "name",
  fileSize: "size",
  fullPath: "fullPath",
  bucket: "bucket",
  FileHash: "hash",

  // Legacy nested fields (for backward compatibility)
  "DigitalSourceAsset.Type": "type",
  "DigitalSourceAsset.MainRepresentation.Format": "format",
  "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.CreateDate":
    "createdAt",
  "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.CreateDate": "createdAt",
  "DigitalSourceAsset.CreateDate": "createdAt",
  "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name": "name",
  "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size": "size",
  "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileSize": "size",
  "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.FullPath":
    "fullPath",
  "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.Bucket": "bucket",
  "Metadata.Consolidated": "metadata",
  InventoryID: "id",
};

// Pre-computed reverse mapping (card field ID → API field IDs)
export const REVERSE_FIELD_MAPPING: Record<string, string[]> = (() => {
  const reverse: Record<string, string[]> = {};
  Object.entries(FIELD_MAPPING).forEach(([apiId, cardId]) => {
    if (!reverse[cardId]) reverse[cardId] = [];
    reverse[cardId].push(apiId);
  });
  return reverse;
})();

/**
 * Filters fields based on visibility and selected search fields.
 * Extracted from AssetCard render body into a pure function.
 */
export function getVisibleFields(
  fields: AssetField[],
  selectedSearchFields?: string[]
): AssetField[] {
  return fields.filter((field) => {
    if (!field.visible) return false;
    if (!selectedSearchFields || selectedSearchFields.length === 0) return true;

    if (field.id === "name") {
      return selectedSearchFields.some((f) => f.includes("Name") || f === "objectName");
    }
    if (field.id === "createdAt") {
      return selectedSearchFields.some((f) => f.includes("CreateDate") || f === "createdAt");
    }
    if (field.id === "size") {
      return selectedSearchFields.some(
        (f) => f.includes("FileSize") || f.includes("Size") || f === "fileSize"
      );
    }
    if (field.id === "fullPath") {
      return selectedSearchFields.some(
        (f) => f.includes("FullPath") || f.includes("Path") || f === "fullPath"
      );
    }

    const apiFieldIds = REVERSE_FIELD_MAPPING[field.id] || [];
    return apiFieldIds.some((apiFieldId) => selectedSearchFields.includes(apiFieldId));
  });
}
