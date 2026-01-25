import React, { useState, useEffect } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
  Typography,
  Box,
  Alert,
  IconButton,
  CircularProgress,
  alpha,
  useTheme,
} from "@mui/material";
import { Close as CloseIcon, Save as SaveIcon } from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { useCreateDashboardPreset } from "@/api/hooks/useDashboard";
import { useDashboardStore } from "../store/dashboardStore";

const MAX_NAME_LENGTH = 100;
const MAX_DESCRIPTION_LENGTH = 500;
const MAX_PRESETS = 5;

interface SavePresetDialogProps {
  open: boolean;
  onClose: () => void;
  currentPresetCount: number;
}

export const SavePresetDialog: React.FC<SavePresetDialogProps> = ({
  open,
  onClose,
  currentPresetCount,
}) => {
  const theme = useTheme();
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [nameError, setNameError] = useState<string | null>(null);

  const layout = useDashboardStore((state) => state.layout);
  const setActivePreset = useDashboardStore((state) => state.setActivePreset);

  const createPresetMutation = useCreateDashboardPreset();

  // Reset form when dialog opens
  useEffect(() => {
    if (open) {
      setName("");
      setDescription("");
      setNameError(null);
    }
  }, [open]);

  const validateName = (value: string): boolean => {
    if (!value.trim()) {
      setNameError(t("dashboard.saveDialog.nameRequired", "Name is required"));
      return false;
    }
    if (value.length > MAX_NAME_LENGTH) {
      setNameError(
        t("dashboard.saveDialog.nameTooLong", "Name cannot exceed {{max}} characters", {
          max: MAX_NAME_LENGTH,
        })
      );
      return false;
    }
    setNameError(null);
    return true;
  };

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setName(value);
    if (nameError) {
      validateName(value);
    }
  };

  const handleDescriptionChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    if (value.length <= MAX_DESCRIPTION_LENGTH) {
      setDescription(value);
    }
  };

  const handleSave = async () => {
    if (!validateName(name)) {
      return;
    }

    try {
      const result = await createPresetMutation.mutateAsync({
        name: name.trim(),
        description: description.trim() || undefined,
        widgets: layout.widgets,
        layouts: layout.layouts,
      });

      // Set the newly created preset as active
      setActivePreset(result.presetId, result.name);

      // Close the dialog
      onClose();
    } catch (error) {
      // Error handling is done in the mutation hook
      console.error("Failed to create preset:", error);
      // Don't close dialog on error so user can retry
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey && name.trim()) {
      e.preventDefault();
      handleSave();
    }
  };

  const isAtLimit = currentPresetCount >= MAX_PRESETS;
  const isNearLimit = currentPresetCount >= MAX_PRESETS - 1;
  const isSaving = createPresetMutation.isPending;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="xs"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 1.5,
          backgroundColor: alpha(theme.palette.background.paper, 0.98),
          backdropFilter: "blur(10px)",
        },
      }}
    >
      <DialogTitle
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          py: 1.5,
          px: 2,
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
          <SaveIcon color="primary" sx={{ fontSize: 20 }} />
          <Typography variant="subtitle1" component="span" fontWeight={600}>
            {t("dashboard.saveDialog.title", "Save Dashboard Layout")}
          </Typography>
        </Box>
        <IconButton
          onClick={onClose}
          size="small"
          aria-label={t("common.close", "Close")}
          sx={{ color: "text.secondary", p: 0.5 }}
        >
          <CloseIcon sx={{ fontSize: 18 }} />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ px: 2, pt: 3, pb: 1.5, overflow: "visible" }}>
        {isAtLimit && (
          <Alert severity="error" sx={{ mb: 1.5, py: 0.5 }}>
            <Typography variant="caption">
              {t(
                "dashboard.saveDialog.limitReached",
                "Maximum {{max}} dashboards reached. Delete one to save a new layout.",
                { max: MAX_PRESETS }
              )}
            </Typography>
          </Alert>
        )}

        {!isAtLimit && isNearLimit && (
          <Alert severity="warning" sx={{ mb: 1.5, py: 0.5 }}>
            <Typography variant="caption">
              {t(
                "dashboard.saveDialog.nearLimit",
                "{{current}}/{{max}} dashboards saved. This will be your last slot.",
                { current: currentPresetCount, max: MAX_PRESETS }
              )}
            </Typography>
          </Alert>
        )}

        <TextField
          autoFocus
          label={t("dashboard.saveDialog.nameLabel", "Dashboard Name")}
          placeholder={t("dashboard.saveDialog.namePlaceholder", "e.g., My Analytics Dashboard")}
          fullWidth
          size="small"
          value={name}
          onChange={handleNameChange}
          onKeyDown={handleKeyDown}
          error={!!nameError}
          helperText={nameError || `${name.length}/${MAX_NAME_LENGTH}`}
          disabled={isAtLimit || isSaving}
          sx={{ mb: 2 }}
          inputProps={{
            maxLength: MAX_NAME_LENGTH,
          }}
        />

        <TextField
          label={t("dashboard.saveDialog.descriptionLabel", "Description (optional)")}
          placeholder={t("dashboard.saveDialog.descriptionPlaceholder", "Add a description...")}
          fullWidth
          size="small"
          multiline
          rows={2}
          value={description}
          onChange={handleDescriptionChange}
          disabled={isAtLimit || isSaving}
          helperText={`${description.length}/${MAX_DESCRIPTION_LENGTH}`}
          inputProps={{
            maxLength: MAX_DESCRIPTION_LENGTH,
          }}
        />

        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1.5 }}>
          {t(
            "dashboard.saveDialog.hint",
            "Your current widget arrangement and sizes will be saved as a new dashboard preset."
          )}
        </Typography>
      </DialogContent>

      <DialogActions sx={{ px: 2, py: 1.5 }}>
        <Button onClick={onClose} disabled={isSaving} size="small">
          {t("common.cancel", "Cancel")}
        </Button>
        <Button
          onClick={handleSave}
          variant="contained"
          size="small"
          disabled={isAtLimit || !name.trim() || isSaving}
          startIcon={
            isSaving ? (
              <CircularProgress size={14} color="inherit" />
            ) : (
              <SaveIcon sx={{ fontSize: 16 }} />
            )
          }
        >
          {isSaving
            ? t("common.saving", "Saving...")
            : t("dashboard.saveDialog.save", "Save Dashboard")}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default SavePresetDialog;
