import React, { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Box,
  Typography,
  Alert,
} from "@mui/material";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import ArrowForwardIcon from "@mui/icons-material/ArrowForward";
import { useTranslation } from "react-i18next";
import { Group } from "@/api/types/group.types";

interface CopyPermissionsDialogProps {
  open: boolean;
  onClose: () => void;
  onCopyPermissions: (sourceGroupId: string, targetGroupId: string) => void;
  groups: Group[];
}

export function CopyPermissionsDialog({
  open,
  onClose,
  onCopyPermissions,
  groups,
}: CopyPermissionsDialogProps) {
  const { t } = useTranslation();
  const [sourceGroupId, setSourceGroupId] = useState("");
  const [targetGroupId, setTargetGroupId] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = () => {
    if (!sourceGroupId) {
      setError(t("permissions.errors.selectSource", "Please select a source group"));
      return;
    }
    if (!targetGroupId) {
      setError(t("permissions.errors.selectTarget", "Please select a target group"));
      return;
    }
    if (sourceGroupId === targetGroupId) {
      setError(t("permissions.errors.sameSrcTarget", "Source and target groups must be different"));
      return;
    }

    onCopyPermissions(sourceGroupId, targetGroupId);
    handleClose();
  };

  const handleClose = () => {
    setSourceGroupId("");
    setTargetGroupId("");
    setError("");
    onClose();
  };

  const sourceGroup = groups.find((g) => g.id === sourceGroupId);
  const targetGroup = groups.find((g) => g.id === targetGroupId);

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <ContentCopyIcon color="primary" />
          <span>{t("permissions.copyPermissions", "Copy Permissions")}</span>
        </Box>
      </DialogTitle>

      <DialogContent>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2.5, pt: 1 }}>
          {error && (
            <Alert severity="error" onClose={() => setError("")}>
              {error}
            </Alert>
          )}

          <Typography variant="body2" color="text.secondary">
            {t(
              "permissions.copyDescription",
              "Copy all permissions from one group to another. This will overwrite the target group's existing permissions."
            )}
          </Typography>

          <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
            <FormControl fullWidth size="small">
              <InputLabel id="source-group-label">
                {t("permissions.sourceGroup", "Source Group")}
              </InputLabel>
              <Select
                labelId="source-group-label"
                value={sourceGroupId}
                label={t("permissions.sourceGroup", "Source Group")}
                onChange={(e) => setSourceGroupId(e.target.value)}
              >
                {groups.map((group) => (
                  <MenuItem key={group.id} value={group.id} disabled={group.id === targetGroupId}>
                    {group.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>

            <ArrowForwardIcon sx={{ color: "text.disabled", flexShrink: 0 }} />

            <FormControl fullWidth size="small">
              <InputLabel id="target-group-label">
                {t("permissions.targetGroup", "Target Group")}
              </InputLabel>
              <Select
                labelId="target-group-label"
                value={targetGroupId}
                label={t("permissions.targetGroup", "Target Group")}
                onChange={(e) => setTargetGroupId(e.target.value)}
              >
                {groups.map((group) => (
                  <MenuItem key={group.id} value={group.id} disabled={group.id === sourceGroupId}>
                    {group.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Box>

          {sourceGroup && targetGroup && (
            <Alert severity="warning" sx={{ mt: 1 }}>
              <Typography variant="body2">
                All permissions from <strong>{sourceGroup.name}</strong> will be copied to{" "}
                <strong>{targetGroup.name}</strong>. This action will overwrite {targetGroup.name}
                &apos;s current permissions.
              </Typography>
            </Alert>
          )}
        </Box>
      </DialogContent>

      <DialogActions sx={{ p: 2.5 }}>
        <Button onClick={handleClose} color="inherit">
          {t("common.cancel", "Cancel")}
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          color="primary"
          startIcon={<ContentCopyIcon />}
          disabled={!sourceGroupId || !targetGroupId}
        >
          {t("permissions.copyPermissions", "Copy Permissions")}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
