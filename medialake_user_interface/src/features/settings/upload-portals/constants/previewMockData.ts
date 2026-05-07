/**
 * Preview mock data rendered inside `PortalPreviewRenderer`.
 *
 * The preview panel is non-interactive and must not hit the network. These
 * constants stand in for real portal configuration so admins see a realistic
 * layout while they tune appearance.
 */

import type { PortalDestination, PortalMetadataField } from "@/api/types/api.types";

/**
 * Three example metadata fields shown in the mock upload form. Mirrors the
 * shape real portals store so the preview feels representative.
 */
export const PREVIEW_MOCK_METADATA_FIELDS: PortalMetadataField[] = [
  { label: "Your Name", type: "text", required: true, order: 0 },
  { label: "Email", type: "email", required: true, order: 1 },
  { label: "Department", type: "text", required: false, order: 2 },
];

/**
 * Single mock destination — the preview does not expose a destination picker,
 * it just demonstrates where files would land if the portal is published.
 */
export const PREVIEW_MOCK_DESTINATIONS: PortalDestination[] = [
  {
    destinationId: "preview-destination",
    friendlyName: "Project Assets",
    connectorId: "preview-connector",
    rootPath: "project-assets",
    allowBrowsing: false,
    allowFolderCreation: false,
    order: 0,
  },
];
