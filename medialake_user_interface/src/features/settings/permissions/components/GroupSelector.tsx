import React from "react";
import {
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  SelectChangeEvent,
  Box,
  Typography,
  Paper,
  Button,
  IconButton,
  Tooltip,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import GroupIcon from "@mui/icons-material/Group";
import SecurityIcon from "@mui/icons-material/Security";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import { Group } from "@/api/types/group.types";

interface GroupSelectorProps {
  groups: Group[];
  selectedGroupId: string;
  onGroupChange: (groupId: string) => void;
  onCreateGroupClick?: () => void;
  onDeleteGroupClick?: () => void;
}

export function GroupSelector({
  groups,
  selectedGroupId,
  onGroupChange,
  onCreateGroupClick,
  onDeleteGroupClick,
}: GroupSelectorProps) {
  const { t } = useTranslation();

  const handleChange = (event: SelectChangeEvent) => {
    onGroupChange(event.target.value as string);
  };

  const selectedGroup = groups.find((g) => g.id === selectedGroupId);

  return (
    <Paper elevation={0} variant="outlined" sx={{ p: 2.5, bgcolor: "action.hover" }}>
      <Box
        sx={{
          display: "flex",
          flexDirection: { xs: "column", md: "row" },
          gap: 2.5,
          alignItems: { xs: "flex-start", md: "center" },
          justifyContent: "space-between",
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
          <Box
            sx={{
              p: 1,
              bgcolor: "primary.light",
              borderRadius: 2,
              display: "flex",
              color: "primary.contrastText",
            }}
          >
            <SecurityIcon />
          </Box>
          <Box>
            <Typography variant="subtitle1" fontWeight="bold">
              {t("permissions.groupConfig", "Group Configuration")}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {t("permissions.selectGroup", "Select a group to manage its permissions")}
            </Typography>
          </Box>
        </Box>

        <Box sx={{ display: "flex", gap: 1.5, alignItems: "center" }}>
          <FormControl size="small" sx={{ minWidth: 200, bgcolor: "background.paper" }}>
            <InputLabel id="group-select-label">
              {t("permissions.selectGroupLabel", "Select Group")}
            </InputLabel>
            <Select
              labelId="group-select-label"
              id="group-select"
              value={selectedGroupId}
              label={t("permissions.selectGroupLabel", "Select Group")}
              onChange={handleChange}
            >
              {groups.map((group) => (
                <MenuItem key={group.id} value={group.id}>
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    <GroupIcon sx={{ fontSize: 16, color: "text.secondary" }} />
                    <span>{group.name}</span>
                  </Box>
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          {onCreateGroupClick && (
            <Button
              variant="outlined"
              color="primary"
              startIcon={<AddIcon />}
              onClick={onCreateGroupClick}
              size="medium"
            >
              {t("permissions.newGroup", "New Group")}
            </Button>
          )}

          {onDeleteGroupClick && selectedGroupId && (
            <Tooltip title={t("permissions.deleteGroup", "Delete Group")}>
              <IconButton
                color="error"
                onClick={onDeleteGroupClick}
                size="medium"
                aria-label={t("permissions.deleteGroup", "Delete Group")}
              >
                <DeleteIcon />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      </Box>

      {selectedGroup && (
        <Box sx={{ mt: 2, pt: 2, borderTop: 1, borderColor: "divider" }}>
          <Typography variant="body2" color="text.secondary">
            <strong>{t("common.labels.description", "Description")}:</strong>{" "}
            {selectedGroup.description}
          </Typography>
        </Box>
      )}
    </Paper>
  );
}
