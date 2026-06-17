import React, { useCallback, useMemo } from "react";
import { Box, Stack, Typography } from "@mui/material";

import type { PortalMetadataField } from "@/api/types/api.types";
import { useGetCollections } from "@/api/hooks/useCollections";

import MetadataFieldBuilder, { type CollectionOption } from "../../MetadataFieldBuilder";
import { usePortalEditorStore } from "../../../stores/usePortalEditorStore";

/**
 * Module-level empty array used as the fallback when the store has no
 * metadata fields. A shared reference keeps the Zustand selector stable so
 * unrelated store writes do not trigger a re-render here.
 */
const EMPTY_METADATA_FIELDS: readonly PortalMetadataField[] = [];

/**
 * FieldConfigurationSection
 *
 * Owns the metadata field builder — the surface where admins configure the
 * fields they dragged onto pages in "Pages & Workflow": label, type
 * (text / email / number / dropdown / radio / checkboxes / tags / yes-no),
 * required toggle, and per-type choices for the choice-based types.
 *
 * This section sits directly under "Pages & Workflow" in the sidebar so the
 * place you place a field and the place you configure it are adjacent. The
 * upload limits (max file size, files per session, allowed file types) live in
 * the separate "Upload Limits & File Settings" section.
 *
 * Store integration:
 *   Reads `metadataFields` via a narrow selector on `portalData`; writes the
 *   field array back through `updatePortalData`, and routes label edits through
 *   the atomic `renameField` action so the field's `label` and every
 *   referencing page element's `fieldKey` stay in sync.
 */
const FieldConfigurationSection: React.FC = () => {
  const metadataFields = usePortalEditorStore(
    (s) =>
      (s.portalData?.metadataFields as PortalMetadataField[] | undefined) ??
      (EMPTY_METADATA_FIELDS as PortalMetadataField[])
  );
  const updatePortalData = usePortalEditorStore((s) => s.updatePortalData);
  const renameField = usePortalEditorStore((s) => s.renameField);

  // Collections the admin can offer in a collection-picker field's allow-list.
  // Fetched here (the section is mounted inside the app's query provider) and
  // passed into the builder, which stays decoupled/testable.
  const { data: collectionsResponse } = useGetCollections();
  const availableCollections = useMemo<CollectionOption[]>(
    () => (collectionsResponse?.data ?? []).map((c) => ({ id: c.id, name: c.name })),
    [collectionsResponse]
  );

  const handleMetadataFieldsChange = useCallback(
    (fields: PortalMetadataField[]) => {
      updatePortalData({ metadataFields: fields });
    },
    [updatePortalData]
  );

  const handleRenameField = useCallback(
    (oldFieldKey: string, newLabel: string) => {
      renameField(oldFieldKey, newLabel);
    },
    [renameField]
  );

  return (
    <Stack spacing={2}>
      <Box>
        <Typography variant="subtitle2" gutterBottom>
          Fields
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
          Configure the metadata fields collected on your pages. For dropdown, radio, checkbox, and
          tag fields, add the choices respondents can pick from.
        </Typography>
        <MetadataFieldBuilder
          fields={metadataFields}
          onChange={handleMetadataFieldsChange}
          onRenameField={handleRenameField}
          availableCollections={availableCollections}
        />
      </Box>
    </Stack>
  );
};

export { FieldConfigurationSection };
export default React.memo(FieldConfigurationSection);
