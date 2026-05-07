import React, { useCallback, useState } from "react";
import { Box, MenuItem, Select, Stack, TextField, Typography } from "@mui/material";

import type { PortalMetadataField } from "@/api/types/api.types";

import MetadataFieldBuilder from "../../MetadataFieldBuilder";
import { usePortalEditorStore } from "../../../stores/usePortalEditorStore";

/**
 * File-size unit options for the max-file-size input. Only MB and GB are
 * supported (matching the legacy step 4); values are stored in bytes on
 * `portalData.maxFileSizeBytes`.
 */
type SizeUnit = "MB" | "GB";

const BYTES_PER_MB = 1024 * 1024;
const BYTES_PER_GB = 1024 * 1024 * 1024;

/**
 * Module-level empty array used as the fallback when the store has no
 * metadata fields. A shared reference keeps the Zustand selector stable so
 * unrelated store writes do not trigger a re-render here.
 */
const EMPTY_METADATA_FIELDS: readonly PortalMetadataField[] = [];

/** Stable empty-array default for the allowedFileTypes selector. */
const EMPTY_FILE_TYPES: string[] = [];

/**
 * Decide whether a given byte count is best expressed in GB.
 *
 * Mirrors the legacy step: we prefer GB when the value is an integer >= 1
 * GB, otherwise fall back to MB. This means an admin who entered `2 GB` // i18n-ignore
 * sees `2` / `GB` on reopen, while someone who entered `1500 MB` sees // i18n-ignore
 * `1500` / `MB` (not `1.46 GB`). // i18n-ignore
 */
const pickSizeUnit = (bytes: number | undefined): SizeUnit => {
  if (!bytes) return "MB";
  const gb = bytes / BYTES_PER_GB;
  return gb >= 1 && Number.isInteger(gb) ? "GB" : "MB";
};

const bytesToDisplayValue = (bytes: number | undefined, unit: SizeUnit): string => {
  if (!bytes) return "";
  if (unit === "GB") {
    const gb = bytes / BYTES_PER_GB;
    return String(gb);
  }
  return String(bytes / BYTES_PER_MB);
};

/**
 * MetadataSection
 *
 * Ports the legacy `PortalFormStep4MetadataLimits` dialog step into the
 * visual editor sidebar. Embeds the existing {@link MetadataFieldBuilder}
 * unmodified, a file-size-limit input with an MB / GB unit selector, and
 * a files-per-session limit input (Requirement 9.3).
 *
 * Store integration:
 *   Reads `metadataFields`, `maxFileSizeBytes`, and `maxFilesPerSession`
 *   via narrow selectors on `portalData`; writes each field back through
 *   `updatePortalData`. Local React state tracks the size input's display
 *   value and unit so the user can switch between MB and GB without losing
 *   typed digits. Field-level error rendering wires up in task 5.9.
 */
const MetadataSection: React.FC = () => {
  const metadataFields = usePortalEditorStore(
    (s) =>
      (s.portalData?.metadataFields as PortalMetadataField[] | undefined) ??
      (EMPTY_METADATA_FIELDS as PortalMetadataField[])
  );
  const maxFileSizeBytes = usePortalEditorStore(
    (s) => s.portalData?.maxFileSizeBytes as number | undefined
  );
  const maxFilesPerSession = usePortalEditorStore(
    (s) => s.portalData?.maxFilesPerSession as number | undefined
  );
  const allowedFileTypes = usePortalEditorStore(
    (s) => (s.portalData?.allowedFileTypes as string[] | undefined) ?? EMPTY_FILE_TYPES
  );
  const updatePortalData = usePortalEditorStore((s) => s.updatePortalData);

  // Local UI state for the size input: we keep the display value and unit
  // independent of the persisted byte count so the user can type `2.5`
  // without the MB/GB conversion rounding mid-stroke.
  const [sizeUnit, setSizeUnit] = useState<SizeUnit>(() => pickSizeUnit(maxFileSizeBytes));
  const [sizeValue, setSizeValue] = useState<string>(() =>
    bytesToDisplayValue(maxFileSizeBytes, pickSizeUnit(maxFileSizeBytes))
  );

  // When the underlying byte count changes externally (e.g. draft rehydrate
  // or reset), reset the local mirror.
  React.useEffect(() => {
    setSizeUnit((prevUnit) => {
      const nextUnit = pickSizeUnit(maxFileSizeBytes);
      // Preserve the user's selected unit unless the store forces a change
      // (e.g. from MB to GB because of a reset). The comparison is cheap
      // and `sizeValue` is recalculated below regardless.
      return nextUnit === prevUnit ? prevUnit : nextUnit;
    });
    setSizeValue(() => bytesToDisplayValue(maxFileSizeBytes, pickSizeUnit(maxFileSizeBytes)));
  }, [maxFileSizeBytes]);

  const commitSize = useCallback(
    (value: string, unit: SizeUnit) => {
      const num = Number.parseFloat(value);
      if (Number.isFinite(num) && num > 0) {
        const bytes = unit === "GB" ? num * BYTES_PER_GB : num * BYTES_PER_MB;
        updatePortalData({ maxFileSizeBytes: bytes });
      } else {
        // Either empty input or non-positive: clear the limit entirely.
        updatePortalData({ maxFileSizeBytes: undefined });
      }
    },
    [updatePortalData]
  );

  const handleSizeValueChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const next = event.target.value;
      setSizeValue(next);
      commitSize(next, sizeUnit);
    },
    [commitSize, sizeUnit]
  );

  const handleSizeUnitChange = useCallback(
    (event: { target: { value: unknown } }) => {
      const nextUnit = event.target.value as SizeUnit;
      setSizeUnit(nextUnit);
      commitSize(sizeValue, nextUnit);
    },
    [commitSize, sizeValue]
  );

  const handleMetadataFieldsChange = useCallback(
    (fields: PortalMetadataField[]) => {
      updatePortalData({ metadataFields: fields });
    },
    [updatePortalData]
  );

  const handleMaxFilesPerSessionChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const raw = event.target.value;
      if (raw === "") {
        updatePortalData({ maxFilesPerSession: undefined });
        return;
      }
      const parsed = Number.parseInt(raw, 10);
      updatePortalData({
        maxFilesPerSession: Number.isFinite(parsed) ? parsed : undefined,
      });
    },
    [updatePortalData]
  );

  const handleAllowedFileTypesChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      const raw = event.target.value;
      // Split by newlines, commas, or semicolons, trim each entry, and
      // filter out empty strings.
      const types = raw
        .split(/[\n,;]+/)
        .map((s) => s.trim())
        .filter(Boolean);
      updatePortalData({ allowedFileTypes: types });
    },
    [updatePortalData]
  );

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="subtitle2" gutterBottom>
          Metadata Fields
        </Typography>
        <MetadataFieldBuilder fields={metadataFields} onChange={handleMetadataFieldsChange} />
      </Box>

      <Stack direction="row" spacing={2} alignItems="flex-end">
        <TextField
          label="Max file size"
          type="number"
          value={sizeValue}
          onChange={handleSizeValueChange}
          size="small"
          sx={{ width: 150 }}
        />
        <Select
          value={sizeUnit}
          onChange={handleSizeUnitChange}
          size="small"
          aria-label="File size unit"
        >
          <MenuItem value="MB">MB</MenuItem>
          <MenuItem value="GB">GB</MenuItem>
        </Select>
      </Stack>

      <TextField
        label="Max files per session"
        type="number"
        value={maxFilesPerSession ?? ""}
        onChange={handleMaxFilesPerSessionChange}
        size="small"
        sx={{ width: 200 }}
      />

      <TextField
        label="Allowed file types"
        value={allowedFileTypes.join("\n")}
        onChange={handleAllowedFileTypesChange}
        size="small"
        fullWidth
        multiline
        minRows={2}
        helperText="Leave empty to accept all files. Enter MIME types (image/*, video/*) or extensions (.pdf, .docx), one per line." // i18n-ignore
      />
    </Stack>
  );
};

export { MetadataSection };
export default React.memo(MetadataSection);
