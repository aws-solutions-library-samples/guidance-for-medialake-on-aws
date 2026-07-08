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
 * Slugify an admin-authored field label into the stable `fieldKey` used to
 * reference a metadata field from its page element. Mirrors the helper in
 * `usePortalEditorStore.ts`, `MetadataFieldBuilder.tsx`, and
 * `shared/portalSurveyModel.ts`.
 */
const slug = (label: string): string =>
  label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");

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
  const addMetadataField = usePortalEditorStore((s) => s.addMetadataField);
  const removeMetadataField = usePortalEditorStore((s) => s.removeMetadataField);

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

  // Create a new field through the store so it is placed on a page (and thus
  // appears in the Pages tab and renders on the public portal), rather than the
  // legacy onChange append which created a label-less, unplaced field.
  const handleAddField = useCallback(() => {
    addMetadataField();
  }, [addMetadataField]);

  // Delete a field fully: removes it from the list AND strips its page element
  // so no orphaned element is left behind (which previously broke save).
  const handleRemoveField = useCallback(
    (index: number) => {
      const field = metadataFields[index];
      if (!field) return;
      removeMetadataField(slug(field.label));
    },
    [metadataFields, removeMetadataField]
  );

  return (
    <Stack spacing={2}>
      <Box>
        <Typography variant="subtitle2" gutterBottom>
          Fields
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
          Configure the metadata fields collected on your pages. For dropdown, radio, and checkbox
          fields, add the choices respondents can pick from. Tag fields are free-entry — respondents
          type their own values instead of picking from a fixed list.
        </Typography>
        <MetadataFieldBuilder
          fields={metadataFields}
          onChange={handleMetadataFieldsChange}
          onRenameField={handleRenameField}
          onAddField={handleAddField}
          onRemoveField={handleRemoveField}
          availableCollections={availableCollections}
        />
      </Box>
    </Stack>
  );
};

export { FieldConfigurationSection };
export default React.memo(FieldConfigurationSection);
