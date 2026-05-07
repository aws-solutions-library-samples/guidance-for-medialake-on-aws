import React, { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Box,
  Typography,
  Alert,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import { useTranslation } from "react-i18next";
import { Group } from "@/api/types/group.types";

interface CreateGroupDialogProps {
  open: boolean;
  onClose: () => void;
  onCreateGroup: (
    group: { name: string; id: string; description: string },
    copyFromGroupId?: string
  ) => void;
  existingGroups: Group[];
}

export function CreateGroupDialog({
  open,
  onClose,
  onCreateGroup,
  existingGroups,
}: CreateGroupDialogProps) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [copyFromGroupId, setCopyFromGroupId] = useState<string>("");
  const [error, setError] = useState("");

  const handleSubmit = () => {
    if (!name.trim()) {
      setError(t("permissions.errors.nameRequired", "Group name is required"));
      return;
    }

    const autoId = name
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_|_$/g, "");

    if (!autoId) {
      setError(t("permissions.errors.nameRequired", "Group name is required"));
      return;
    }

    if (existingGroups.some((g) => g.id === autoId)) {
      setError(t("permissions.errors.idExists", "A group with this name already exists"));
      return;
    }

    onCreateGroup(
      {
        name: name.trim(),
        id: autoId,
        description: description.trim() || `Group: ${name.trim()}`,
      },
      copyFromGroupId || undefined
    );

    handleClose();
  };

  const handleClose = () => {
    setName("");
    setDescription("");
    setCopyFromGroupId("");
    setError("");
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <AddIcon color="primary" />
          <span>{t("permissions.createGroup", "Create New Group")}</span>
        </Box>
      </DialogTitle>

      <DialogContent>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2.5, pt: 1 }}>
          {error && (
            <Alert severity="error" onClose={() => setError("")}>
              {error}
            </Alert>
          )}

          <TextField
            label={t("permissions.groupName", "Group Name")}
            placeholder={t("permissions.groupNamePlaceholder", "e.g., Content Manager")}
            value={name}
            onChange={(e) => setName(e.target.value)}
            fullWidth
            required
            autoFocus
          />

          <TextField
            label={t("common.labels.description", "Description")}
            placeholder={t(
              "permissions.groupDescriptionPlaceholder",
              "Describe what this group can do..."
            )}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            fullWidth
            multiline
            rows={2}
          />

          <FormControl fullWidth>
            <InputLabel id="copy-from-label">
              {t("permissions.copyFrom", "Copy Permissions From (Optional)")}
            </InputLabel>
            <Select
              labelId="copy-from-label"
              value={copyFromGroupId}
              label={t("permissions.copyFrom", "Copy Permissions From (Optional)")}
              onChange={(e) => setCopyFromGroupId(e.target.value)}
            >
              <MenuItem value="">
                <em>{t("permissions.startEmpty", "Start with no permissions")}</em>
              </MenuItem>
              {existingGroups.map((group) => (
                <MenuItem key={group.id} value={group.id}>
                  {group.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            {t(
              "permissions.createGroupHint",
              "After creating the group, you can customize its permissions using the permission table."
            )}
          </Typography>
        </Box>
      </DialogContent>

      <DialogActions sx={{ p: 2.5 }}>
        <Button onClick={handleClose} color="inherit">
          {t("common.cancel", "Cancel")}
        </Button>
        <Button onClick={handleSubmit} variant="contained" color="primary" startIcon={<AddIcon />}>
          {t("permissions.createGroup", "Create Group")}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
