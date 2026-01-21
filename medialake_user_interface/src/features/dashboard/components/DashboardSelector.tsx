import React, { useState } from "react";
import {
  Box,
  Button,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Divider,
  Typography,
  CircularProgress,
  Chip,
  alpha,
  useTheme,
} from "@mui/material";
import {
  KeyboardArrowDown as ArrowDownIcon,
  Dashboard as DashboardIcon,
  Save as SaveIcon,
  Settings as SettingsIcon,
  Check as CheckIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import {
  useGetDashboardPresets,
  useApplyDashboardPreset,
  type PresetSummary,
} from "@/api/hooks/useDashboard";
import { useDashboardStore, convertApiLayoutToFrontend } from "../store/dashboardStore";
import { SavePresetDialog } from "./SavePresetDialog";
import { PresetManagementDialog } from "./PresetManagementDialog";

const MAX_PRESETS = 5;

interface DashboardSelectorProps {
  className?: string;
}

export const DashboardSelector: React.FC<DashboardSelectorProps> = ({ className }) => {
  const theme = useTheme();
  const { t } = useTranslation();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [manageDialogOpen, setManageDialogOpen] = useState(false);

  const open = Boolean(anchorEl);

  // Store state
  const activePresetId = useDashboardStore((state) => state.activePresetId);
  const activePresetName = useDashboardStore((state) => state.activePresetName);
  const setLayout = useDashboardStore((state) => state.setLayout);
  const setActivePreset = useDashboardStore((state) => state.setActivePreset);
  const setHasPendingChanges = useDashboardStore((state) => state.setHasPendingChanges);

  // API hooks
  const { data: presets = [], isLoading: isLoadingPresets } = useGetDashboardPresets();
  const applyPresetMutation = useApplyDashboardPreset();

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handlePresetSelect = async (preset: PresetSummary) => {
    handleClose();
    try {
      const result = await applyPresetMutation.mutateAsync(preset.presetId);
      // Update local store with the applied layout
      const frontendLayout = convertApiLayoutToFrontend(result);
      setLayout(frontendLayout);
      setActivePreset(preset.presetId, preset.name);
      setHasPendingChanges(false);
    } catch (error) {
      console.error("Failed to apply preset:", error);
    }
  };

  const handleDefaultSelect = () => {
    handleClose();
    // Clear active preset to indicate using default/custom layout
    setActivePreset(null, null);
  };

  const handleSaveClick = () => {
    handleClose();
    setSaveDialogOpen(true);
  };

  const handleManageClick = () => {
    handleClose();
    setManageDialogOpen(true);
  };

  const displayName = activePresetName || t("dashboard.selector.defaultDashboard", "Dashboard");
  const isApplying = applyPresetMutation.isPending;

  return (
    <Box className={className}>
      <Button
        id="dashboard-selector-button"
        aria-controls={open ? "dashboard-selector-menu" : undefined}
        aria-haspopup="true"
        aria-expanded={open ? "true" : undefined}
        onClick={handleClick}
        disabled={isApplying}
        variant="outlined"
        size="small"
        startIcon={
          isApplying ? (
            <CircularProgress size={14} color="inherit" />
          ) : (
            <DashboardIcon sx={{ fontSize: 18 }} />
          )
        }
        endIcon={<ArrowDownIcon sx={{ fontSize: 18 }} />}
        sx={{
          textTransform: "none",
          fontSize: "0.8125rem",
          py: 0.5,
          px: 1.5,
          minWidth: "auto",
          "& .MuiButton-startIcon": {
            marginRight: 0.5,
          },
          "& .MuiButton-endIcon": {
            marginLeft: 0.5,
          },
        }}
      >
        {displayName}
      </Button>

      <Menu
        id="dashboard-selector-menu"
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        MenuListProps={{
          "aria-labelledby": "dashboard-selector-button",
          dense: true,
        }}
        PaperProps={{
          sx: {
            minWidth: 200,
            maxWidth: 260,
            backgroundColor: alpha(theme.palette.background.paper, 0.98),
            backdropFilter: "blur(10px)",
            borderRadius: 1.5,
            mt: 0.5,
          },
        }}
      >
        {/* Default Dashboard Option */}
        <MenuItem onClick={handleDefaultSelect} selected={!activePresetId}>
          <ListItemIcon sx={{ minWidth: 28 }}>
            {!activePresetId ? (
              <CheckIcon sx={{ fontSize: 16 }} color="primary" />
            ) : (
              <DashboardIcon sx={{ fontSize: 16 }} />
            )}
          </ListItemIcon>
          <ListItemText
            primary={t("dashboard.selector.defaultDashboard", "Dashboard")}
            secondary={t("dashboard.selector.defaultDescription", "Default layout")}
            primaryTypographyProps={{ variant: "body2" }}
            secondaryTypographyProps={{ variant: "caption" }}
          />
        </MenuItem>

        {/* Saved Presets */}
        {isLoadingPresets ? (
          <MenuItem disabled>
            <ListItemIcon sx={{ minWidth: 28 }}>
              <CircularProgress size={14} />
            </ListItemIcon>
            <ListItemText
              primary={t("common.loading", "Loading...")}
              primaryTypographyProps={{ variant: "body2" }}
            />
          </MenuItem>
        ) : presets.length > 0 ? (
          <>
            <Divider sx={{ my: 0.5 }} />
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ px: 1.5, py: 0.25, display: "block", fontSize: "0.7rem" }}
            >
              {t("dashboard.selector.savedDashboards", "Saved Dashboards")}
            </Typography>
            {presets.map((preset) => (
              <MenuItem
                key={preset.presetId}
                onClick={() => handlePresetSelect(preset)}
                selected={activePresetId === preset.presetId}
              >
                <ListItemIcon sx={{ minWidth: 28 }}>
                  {activePresetId === preset.presetId ? (
                    <CheckIcon sx={{ fontSize: 16 }} color="primary" />
                  ) : (
                    <DashboardIcon sx={{ fontSize: 16 }} />
                  )}
                </ListItemIcon>
                <ListItemText
                  primary={preset.name}
                  secondary={`${preset.widgetCount} ${t("dashboard.selector.widgets", "widgets")}`}
                  primaryTypographyProps={{
                    variant: "body2",
                    noWrap: true,
                    sx: { maxWidth: 140 },
                  }}
                  secondaryTypographyProps={{ variant: "caption" }}
                />
              </MenuItem>
            ))}
          </>
        ) : null}

        <Divider sx={{ my: 0.5 }} />

        {/* Actions */}
        <MenuItem onClick={handleSaveClick} disabled={presets.length >= MAX_PRESETS}>
          <ListItemIcon sx={{ minWidth: 28 }}>
            <SaveIcon sx={{ fontSize: 16 }} />
          </ListItemIcon>
          <ListItemText
            primary={t("dashboard.selector.saveCurrentLayout", "Save Current Layout")}
            primaryTypographyProps={{ variant: "body2" }}
          />
        </MenuItem>

        <MenuItem onClick={handleManageClick}>
          <ListItemIcon sx={{ minWidth: 28 }}>
            <SettingsIcon sx={{ fontSize: 16 }} />
          </ListItemIcon>
          <ListItemText
            primary={t("dashboard.selector.manageDashboards", "Manage Dashboards")}
            primaryTypographyProps={{ variant: "body2" }}
          />
        </MenuItem>

        {/* Preset count indicator */}
        <Box sx={{ px: 1.5, py: 0.75, display: "flex", justifyContent: "center" }}>
          <Chip
            size="small"
            label={`${presets.length}/${MAX_PRESETS} ${t(
              "dashboard.selector.dashboardsSaved",
              "dashboards saved"
            )}`}
            variant="outlined"
            sx={{
              height: 20,
              fontSize: "0.7rem",
              borderColor: presets.length >= MAX_PRESETS ? "warning.main" : "divider",
              color: presets.length >= MAX_PRESETS ? "warning.main" : "text.secondary",
            }}
          />
        </Box>
      </Menu>

      {/* Save Preset Dialog */}
      <SavePresetDialog
        open={saveDialogOpen}
        onClose={() => setSaveDialogOpen(false)}
        currentPresetCount={presets.length}
      />

      {/* Preset Management Dialog */}
      <PresetManagementDialog open={manageDialogOpen} onClose={() => setManageDialogOpen(false)} />
    </Box>
  );
};

export default DashboardSelector;
