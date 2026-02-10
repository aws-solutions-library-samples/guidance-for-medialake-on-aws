import React, { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  IconButton,
  List,
  ListItem,
  Paper,
  TextField,
  CircularProgress,
  Chip,
  Tooltip,
  alpha,
  useTheme,
} from "@mui/material";
import {
  Close as CloseIcon,
  Settings as SettingsIcon,
  Dashboard as DashboardIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Check as CheckIcon,
  PlayArrow as ApplyIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import {
  useGetDashboardPresets,
  useApplyDashboardPreset,
  useUpdateDashboardPreset,
  useDeleteDashboardPreset,
  type PresetSummary,
} from "@/api/hooks/useDashboard";
import { useDashboardStore, convertApiLayoutToFrontend } from "../store/dashboardStore";
import { ConfirmDialog } from "./ConfirmDialog";

const MAX_PRESETS = 5;
const MAX_NAME_LENGTH = 100;

interface PresetManagementDialogProps {
  open: boolean;
  onClose: () => void;
}

export const PresetManagementDialog: React.FC<PresetManagementDialogProps> = ({
  open,
  onClose,
}) => {
  const theme = useTheme();
  const { t } = useTranslation();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  // Store state
  const activePresetId = useDashboardStore((state) => state.activePresetId);
  const setLayout = useDashboardStore((state) => state.setLayout);
  const setActivePreset = useDashboardStore((state) => state.setActivePreset);
  const setHasPendingChanges = useDashboardStore((state) => state.setHasPendingChanges);

  // API hooks
  const { data: presets = [], isLoading } = useGetDashboardPresets();
  const applyPresetMutation = useApplyDashboardPreset();
  const updatePresetMutation = useUpdateDashboardPreset();
  const deletePresetMutation = useDeleteDashboardPreset();

  const handleStartEdit = (preset: PresetSummary) => {
    setEditingId(preset.presetId);
    setEditName(preset.name);
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditName("");
  };

  const handleSaveEdit = async (presetId: string) => {
    if (!editName.trim()) return;

    try {
      await updatePresetMutation.mutateAsync({
        presetId,
        data: { name: editName.trim() },
      });
      // If editing the active preset, update the display name
      if (activePresetId === presetId) {
        setActivePreset(presetId, editName.trim());
      }
      setEditingId(null);
      setEditName("");
    } catch (error) {
      console.error("Failed to update preset:", error);
    }
  };

  const handleApply = async (preset: PresetSummary) => {
    try {
      const result = await applyPresetMutation.mutateAsync(preset.presetId);
      const frontendLayout = convertApiLayoutToFrontend(result);
      setLayout(frontendLayout);
      setActivePreset(preset.presetId, preset.name);
      setHasPendingChanges(false);
      onClose();
    } catch (error) {
      console.error("Failed to apply preset:", error);
    }
  };

  const handleDeleteClick = (presetId: string) => {
    setDeleteConfirmId(presetId);
  };

  const handleDeleteConfirm = async () => {
    if (!deleteConfirmId) return;

    try {
      await deletePresetMutation.mutateAsync(deleteConfirmId);
      // If deleting the active preset, clear it
      if (activePresetId === deleteConfirmId) {
        setActivePreset(null, null);
      }
      setDeleteConfirmId(null);
    } catch (error) {
      console.error("Failed to delete preset:", error);
    }
  };

  const handleDeleteCancel = () => {
    setDeleteConfirmId(null);
  };

  const formatDate = (dateString: string) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    } catch {
      return dateString;
    }
  };

  const presetToDelete = presets.find((p) => p.presetId === deleteConfirmId);

  return (
    <>
      <Dialog
        open={open}
        onClose={onClose}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            borderRadius: 2,
            backgroundColor: alpha(theme.palette.background.paper, 0.95),
            backdropFilter: "blur(10px)",
            minHeight: 400,
          },
        }}
      >
        <DialogTitle
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            pb: 1,
          }}
        >
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <SettingsIcon color="primary" />
            <Typography variant="h6" component="span">
              {t("dashboard.manageDialog.title", "Manage Dashboards")}
            </Typography>
          </Box>
          <IconButton
            onClick={onClose}
            size="small"
            aria-label={t("common.close", "Close")}
            sx={{ color: "text.secondary" }}
          >
            <CloseIcon />
          </IconButton>
        </DialogTitle>

        <DialogContent>
          {isLoading ? (
            <Box
              sx={{
                display: "flex",
                justifyContent: "center",
                alignItems: "center",
                py: 8,
              }}
            >
              <CircularProgress />
            </Box>
          ) : presets.length === 0 ? (
            <Box
              sx={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                py: 8,
                textAlign: "center",
              }}
            >
              <DashboardIcon sx={{ fontSize: 64, color: "text.disabled", mb: 2 }} />
              <Typography variant="h6" color="text.secondary">
                {t("dashboard.manageDialog.noPresets", "No saved dashboards")}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {t(
                  "dashboard.manageDialog.noPresetsHint",
                  "Save your current layout to create your first dashboard preset."
                )}
              </Typography>
            </Box>
          ) : (
            <List sx={{ pt: 0 }}>
              {presets.map((preset) => {
                const isEditing = editingId === preset.presetId;
                const isActive = activePresetId === preset.presetId;
                const isApplying =
                  applyPresetMutation.isPending &&
                  applyPresetMutation.variables === preset.presetId;
                const isDeleting =
                  deletePresetMutation.isPending &&
                  deletePresetMutation.variables === preset.presetId;
                const isUpdating =
                  updatePresetMutation.isPending &&
                  updatePresetMutation.variables?.presetId === preset.presetId;

                return (
                  <ListItem key={preset.presetId} disablePadding sx={{ mb: 1.5 }}>
                    <Paper
                      variant="outlined"
                      sx={{
                        width: "100%",
                        p: 2,
                        borderRadius: 2,
                        borderColor: isActive ? "primary.main" : "divider",
                        backgroundColor: isActive
                          ? alpha(theme.palette.primary.main, 0.05)
                          : "transparent",
                        transition: "all 0.2s",
                        "&:hover": {
                          borderColor: isActive ? "primary.main" : "primary.light",
                        },
                      }}
                    >
                      <Box
                        sx={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "flex-start",
                        }}
                      >
                        <Box sx={{ flex: 1, minWidth: 0, mr: 2 }}>
                          {isEditing ? (
                            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                              <TextField
                                value={editName}
                                onChange={(e) => setEditName(e.target.value)}
                                size="small"
                                autoFocus
                                fullWidth
                                inputProps={{ maxLength: MAX_NAME_LENGTH }}
                                onKeyDown={(e) => {
                                  if (e.key === "Enter") {
                                    handleSaveEdit(preset.presetId);
                                  } else if (e.key === "Escape") {
                                    handleCancelEdit();
                                  }
                                }}
                              />
                              <IconButton
                                size="small"
                                color="primary"
                                onClick={() => handleSaveEdit(preset.presetId)}
                                disabled={!editName.trim() || isUpdating}
                              >
                                {isUpdating ? (
                                  <CircularProgress size={18} />
                                ) : (
                                  <CheckIcon fontSize="small" />
                                )}
                              </IconButton>
                              <IconButton size="small" onClick={handleCancelEdit}>
                                <CloseIcon fontSize="small" />
                              </IconButton>
                            </Box>
                          ) : (
                            <>
                              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                                <DashboardIcon
                                  fontSize="small"
                                  sx={{ color: isActive ? "primary.main" : "text.secondary" }}
                                />
                                <Typography
                                  variant="subtitle1"
                                  fontWeight={500}
                                  noWrap
                                  sx={{ maxWidth: 200 }}
                                >
                                  {preset.name}
                                </Typography>
                                {isActive && (
                                  <Chip
                                    label={t("dashboard.manageDialog.active", "Active")}
                                    size="small"
                                    color="primary"
                                    variant="outlined"
                                  />
                                )}
                              </Box>
                              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                                {preset.widgetCount}{" "}
                                {t("dashboard.manageDialog.widgets", "widgets")} •{" "}
                                {t("dashboard.manageDialog.updated", "Updated")}{" "}
                                {formatDate(preset.updatedAt)}
                              </Typography>
                              {preset.description && (
                                <Typography
                                  variant="body2"
                                  color="text.secondary"
                                  sx={{
                                    mt: 1,
                                    fontStyle: "italic",
                                    overflow: "hidden",
                                    textOverflow: "ellipsis",
                                    display: "-webkit-box",
                                    WebkitLineClamp: 2,
                                    WebkitBoxOrient: "vertical",
                                  }}
                                >
                                  {preset.description}
                                </Typography>
                              )}
                            </>
                          )}
                        </Box>

                        {!isEditing && (
                          <Box sx={{ display: "flex", gap: 0.5, flexShrink: 0 }}>
                            <Tooltip title={t("dashboard.manageDialog.apply", "Apply")}>
                              <IconButton
                                size="small"
                                color="primary"
                                onClick={() => handleApply(preset)}
                                disabled={isActive || isApplying}
                              >
                                {isApplying ? (
                                  <CircularProgress size={18} />
                                ) : (
                                  <ApplyIcon fontSize="small" />
                                )}
                              </IconButton>
                            </Tooltip>
                            <Tooltip title={t("dashboard.manageDialog.edit", "Edit")}>
                              <IconButton size="small" onClick={() => handleStartEdit(preset)}>
                                <EditIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                            <Tooltip title={t("dashboard.manageDialog.delete", "Delete")}>
                              <IconButton
                                size="small"
                                color="error"
                                onClick={() => handleDeleteClick(preset.presetId)}
                                disabled={isDeleting}
                              >
                                {isDeleting ? (
                                  <CircularProgress size={18} />
                                ) : (
                                  <DeleteIcon fontSize="small" />
                                )}
                              </IconButton>
                            </Tooltip>
                          </Box>
                        )}
                      </Box>
                    </Paper>
                  </ListItem>
                );
              })}
            </List>
          )}

          {/* Preset count indicator */}
          <Box sx={{ display: "flex", justifyContent: "center", mt: 2 }}>
            <Chip
              size="small"
              label={`${presets.length}/${MAX_PRESETS} ${t(
                "dashboard.selector.dashboardsSaved",
                "dashboards saved"
              )}`}
              variant="outlined"
              sx={{
                borderColor: presets.length >= MAX_PRESETS ? "warning.main" : "divider",
                color: presets.length >= MAX_PRESETS ? "warning.main" : "text.secondary",
              }}
            />
          </Box>
        </DialogContent>

        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={onClose}>{t("common.close", "Close")}</Button>
        </DialogActions>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={!!deleteConfirmId}
        title={t("dashboard.deleteDialog.title", "Delete Dashboard?")}
        message={t(
          "dashboard.deleteDialog.message",
          'Are you sure you want to delete "{{name}}"? This action cannot be undone.',
          { name: presetToDelete?.name || "" }
        )}
        confirmLabel={t("common.delete", "Delete")}
        cancelLabel={t("common.cancel", "Cancel")}
        onConfirm={handleDeleteConfirm}
        onCancel={handleDeleteCancel}
        confirmColor="error"
        isLoading={deletePresetMutation.isPending}
      />
    </>
  );
};

export default PresetManagementDialog;
