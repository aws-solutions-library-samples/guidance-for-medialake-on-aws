import React, { useCallback, useState } from "react";
import {
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Chip,
  Dialog,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  Stack,
  Switch,
  Typography,
} from "@mui/material";
import { Add as AddIcon, Delete as DeleteIcon, Edit as EditIcon } from "@mui/icons-material";

import type { PortalDestination } from "@/api/types/api.types";

import DestinationForm from "../../DestinationForm";
import { usePortalEditorStore } from "../../../stores/usePortalEditorStore";

/** Stable empty-array default for the destinations selector. */
const EMPTY_DESTINATIONS: PortalDestination[] = [];

/**
 * DestinationsSection
 *
 * Ports the legacy `PortalFormStep3Destinations` dialog step into the
 * visual editor sidebar. Preserves the destination list with add / edit /
 * remove controls and the `structuredPathMode` toggle, and reuses the
 * existing {@link DestinationForm} (from `../../DestinationForm`)
 * unmodified (Requirement 9.2).
 *
 * The legacy source did not implement reorder, so neither does this port;
 * reorder is noted in the spec as a nice-to-have but not in scope.
 *
 * Store integration:
 *   Reads `destinations` and `structuredPathMode` via narrow selectors on
 *   `portalData` and writes them back through `updatePortalData`. Field-
 *   level error rendering is deferred to task 5.9; the legacy `errors`
 *   prop is intentionally omitted here.
 */
const DestinationsSection: React.FC = () => {
  const destinations = usePortalEditorStore(
    (s) => (s.portalData?.destinations as PortalDestination[] | undefined) ?? EMPTY_DESTINATIONS
  );
  const structuredPathMode = usePortalEditorStore(
    (s) => (s.portalData?.structuredPathMode as boolean | undefined) ?? false
  );
  const updatePortalData = usePortalEditorStore((s) => s.updatePortalData);

  // Field-level validation errors for this section
  const sectionErrors = usePortalEditorStore((s) => s.validationErrors.destinations);
  const destinationsError = sectionErrors?.find((e) => e.field === "destinations")?.message;

  // Local UI state: `editingIndex === null && !isAdding` means no form is
  // open. Mirror the legacy dialog's two-flag approach so the "Add" button
  // and the inline form never render simultaneously.
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [isAdding, setIsAdding] = useState(false);

  const handleStructuredPathModeChange = useCallback(
    (_event: React.ChangeEvent<HTMLInputElement>, checked: boolean) => {
      updatePortalData({ structuredPathMode: checked });
    },
    [updatePortalData]
  );

  const handleSaveDestination = useCallback(
    (dest: PortalDestination) => {
      // Splice the updated destination back at the same position (edit
      // path) or append (add path) so order is preserved. Mirrors the
      // legacy step exactly.
      const updated = [...destinations];
      if (editingIndex !== null) {
        updated[editingIndex] = dest;
      } else {
        updated.push(dest);
      }
      updatePortalData({ destinations: updated });
      setEditingIndex(null);
      setIsAdding(false);
    },
    [destinations, editingIndex, updatePortalData]
  );

  const handleCancel = useCallback(() => {
    setIsAdding(false);
    setEditingIndex(null);
  }, []);

  const handleRemove = useCallback(
    (index: number) => {
      updatePortalData({
        destinations: destinations.filter((_, i) => i !== index),
      });
    },
    [destinations, updatePortalData]
  );

  const handleEdit = useCallback((index: number) => {
    setEditingIndex(index);
  }, []);

  const handleStartAdd = useCallback(() => {
    setIsAdding(true);
  }, []);

  const isFormOpen = isAdding || editingIndex !== null;

  return (
    <Stack spacing={2}>
      {destinationsError && destinations.length === 0 && (
        <Typography variant="body2" color="error" sx={{ mb: 1 }}>
          {destinationsError}
        </Typography>
      )}

      <FormControlLabel
        control={<Switch checked={structuredPathMode} onChange={handleStructuredPathModeChange} />}
        label="Structured Path Mode"
      />

      {destinations.map((dest, i) => (
        <Card key={dest.destinationId} variant="outlined">
          <CardContent sx={{ pb: 1 }}>
            <Typography variant="subtitle2">{dest.friendlyName}</Typography>
            <Typography variant="body2" color="text.secondary">
              Root: {dest.rootPath || "/"}
            </Typography>
            <Box sx={{ mt: 1, display: "flex", gap: 0.5 }}>
              {dest.allowBrowsing && <Chip label="Browsing" size="small" />}
              {dest.allowFolderCreation && <Chip label="Folder Creation" size="small" />}
            </Box>
          </CardContent>
          <CardActions>
            <IconButton
              size="small"
              onClick={() => handleEdit(i)}
              aria-label={`Edit ${dest.friendlyName}`}
            >
              <EditIcon fontSize="small" />
            </IconButton>
            <IconButton
              size="small"
              onClick={() => handleRemove(i)}
              aria-label={`Remove ${dest.friendlyName}`}
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
          </CardActions>
        </Card>
      ))}

      {isFormOpen && (
        <Dialog
          open
          onClose={handleCancel}
          maxWidth="sm"
          fullWidth
          aria-labelledby="destination-form-dialog-title"
        >
          <DialogTitle id="destination-form-dialog-title">
            {editingIndex !== null ? "Edit Destination" : "Add Destination"}
          </DialogTitle>
          <DialogContent>
            <DestinationForm
              destination={editingIndex !== null ? destinations[editingIndex] : undefined}
              structuredPathMode={structuredPathMode}
              onSave={handleSaveDestination}
              onCancel={handleCancel}
            />
          </DialogContent>
        </Dialog>
      )}

      {!isFormOpen && (
        <Button startIcon={<AddIcon />} onClick={handleStartAdd}>
          Add Destination
        </Button>
      )}

      {destinations.length === 0 && !isFormOpen && (
        <Typography variant="body2" color="error">
          At least one destination is required.
        </Typography>
      )}
    </Stack>
  );
};

export { DestinationsSection };
export default React.memo(DestinationsSection);
