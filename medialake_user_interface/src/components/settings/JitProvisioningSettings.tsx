import React, { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  FormControl,
  FormControlLabel,
  FormHelperText,
  InputLabel,
  MenuItem,
  Select,
  Snackbar,
  Switch,
  Typography,
} from "@mui/material";
import { Save as SaveIcon, Refresh as RefreshIcon } from "@mui/icons-material";
import { useGetGroups } from "@/api/hooks/useGroups";
import { useJitProvisioningSettings } from "@/api/hooks/useJitProvisioningSettings";
import { useUpdateJitProvisioningSettings } from "@/api/hooks/useUpdateJitProvisioningSettings";

/**
 * Configures which group a user is placed in the first time they sign in
 * through an external identity provider (just-in-time provisioning).
 *
 * The assignment happens once per user. Moving somebody to a different group
 * afterwards is never undone by a later sign-in, so this setting only affects
 * users who have not signed in before.
 */
const JitProvisioningSettings: React.FC = () => {
  const { t } = useTranslation();

  const settingsQuery = useJitProvisioningSettings();
  const groupsQuery = useGetGroups();
  const updateMutation = useUpdateJitProvisioningSettings();

  const saved = settingsQuery.data?.data;

  const [enabled, setEnabled] = useState(false);
  const [defaultGroupId, setDefaultGroupId] = useState("");
  const [showSuccess, setShowSuccess] = useState(false);

  // Seed the draft from the server once it arrives, and whenever it changes
  // underneath us (for example after another administrator saves).
  useEffect(() => {
    if (saved) {
      setEnabled(saved.enabled);
      setDefaultGroupId(saved.defaultGroupId || "");
    }
  }, [saved?.enabled, saved?.defaultGroupId, saved?.updatedAt]);

  const groups = groupsQuery.data ?? [];

  const hasChanges = useMemo(() => {
    if (!saved) return false;
    return enabled !== saved.enabled || defaultGroupId !== (saved.defaultGroupId || "");
  }, [enabled, defaultGroupId, saved]);

  // A group must be chosen before the feature can be switched on, otherwise
  // there would be nothing to assign.
  const missingGroup = enabled && !defaultGroupId;
  const canSave = hasChanges && !missingGroup && !updateMutation.isPending;

  const handleReset = () => {
    if (saved) {
      setEnabled(saved.enabled);
      setDefaultGroupId(saved.defaultGroupId || "");
    }
  };

  const handleSave = async () => {
    try {
      await updateMutation.mutateAsync({
        enabled,
        defaultGroupId,
        expectedUpdatedAt: saved?.updatedAt ?? null,
      });
      setShowSuccess(true);
    } catch {
      // Errors are surfaced by the mutation hook's error modal.
    }
  };

  if (settingsQuery.isLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", py: 6 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (settingsQuery.isError) {
    return (
      <Alert severity="error">
        {t(
          "settings.systemSettings.jitProvisioning.loadError",
          "Could not load the just-in-time provisioning settings."
        )}
      </Alert>
    );
  }

  return (
    <Box sx={{ height: "100%", overflow: "auto", pr: 1 }}>
      <Typography variant="h6" gutterBottom>
        {t("settings.systemSettings.jitProvisioning.title", "Just-In-Time User Provisioning")}
      </Typography>

      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        {t(
          "settings.systemSettings.jitProvisioning.description",
          "Choose the group assigned to users the first time they sign in through an external identity provider. The group is applied once per user, so moving somebody to a different group later is never undone by a subsequent sign-in."
        )}
      </Typography>

      {saved && !saved.capabilityEnabled && (
        <Alert severity="info" sx={{ mb: 3 }}>
          {t(
            "settings.systemSettings.jitProvisioning.capabilityDisabled",
            "Just-in-time provisioning is not enabled for this deployment. Set authZ.jit_provisioning.enabled in the deployment configuration and redeploy before these settings take effect."
          )}
        </Alert>
      )}

      <FormControlLabel
        control={
          // Labelled by the surrounding FormControlLabel.
          <Switch checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
        }
        label={t(
          "settings.systemSettings.jitProvisioning.enabledLabel",
          "Assign a default group to new federated users"
        )}
        sx={{ mb: 3, display: "block" }}
      />

      <FormControl
        sx={{ minWidth: 320, mb: 1, display: "block", maxWidth: 480 }}
        error={missingGroup}
        disabled={!enabled || groupsQuery.isLoading}
        fullWidth
      >
        <InputLabel id="jit-default-group-label">
          {t("settings.systemSettings.jitProvisioning.defaultGroupLabel", "Default group")}
        </InputLabel>
        <Select
          labelId="jit-default-group-label"
          id="jit-default-group"
          value={defaultGroupId}
          label={t("settings.systemSettings.jitProvisioning.defaultGroupLabel", "Default group")}
          onChange={(e) => setDefaultGroupId(e.target.value)}
        >
          {groups.length === 0 && (
            <MenuItem value="" disabled>
              {t("settings.systemSettings.jitProvisioning.noGroups", "No groups available")}
            </MenuItem>
          )}
          {groups.map((group) => (
            <MenuItem key={group.id} value={group.id}>
              {group.name || group.id}
            </MenuItem>
          ))}
        </Select>
        <FormHelperText>
          {missingGroup
            ? t(
                "settings.systemSettings.jitProvisioning.groupRequired",
                "Choose a group before enabling just-in-time provisioning."
              )
            : t(
                "settings.systemSettings.jitProvisioning.defaultGroupHelp",
                "New federated users receive this group's permissions on their first sign-in."
              )}
        </FormHelperText>
      </FormControl>

      {saved?.updatedAt && (
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 2 }}>
          {t("settings.systemSettings.jitProvisioning.lastUpdated", "Last updated")}:{" "}
          {new Date(saved.updatedAt).toLocaleString()}
          {saved.updatedBy ? ` — ${saved.updatedBy}` : ""}
        </Typography>
      )}

      <Box sx={{ display: "flex", gap: 2, mt: 4 }}>
        <Button
          variant="contained"
          startIcon={<SaveIcon />}
          onClick={handleSave}
          disabled={!canSave}
        >
          {updateMutation.isPending ? t("common.saving", "Saving...") : t("common.save", "Save")}
        </Button>
        <Button
          variant="outlined"
          startIcon={<RefreshIcon />}
          onClick={handleReset}
          disabled={!hasChanges || updateMutation.isPending}
        >
          {t("common.cancel", "Cancel")}
        </Button>
      </Box>

      <Snackbar open={showSuccess} autoHideDuration={4000} onClose={() => setShowSuccess(false)}>
        <Alert severity="success" onClose={() => setShowSuccess(false)}>
          {t(
            "settings.systemSettings.jitProvisioning.saveSuccess",
            "Just-in-time provisioning settings saved."
          )}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default JitProvisioningSettings;
