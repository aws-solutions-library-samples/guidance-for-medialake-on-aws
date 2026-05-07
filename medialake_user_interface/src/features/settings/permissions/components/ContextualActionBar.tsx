import React from "react";
import {
  Box,
  TextField,
  InputAdornment,
  Button,
  Typography,
  Chip,
  CircularProgress,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import SearchIcon from "@mui/icons-material/Search";
import { colorTokens } from "@/theme/tokens";
import SaveIcon from "@mui/icons-material/Save";
import CloseIcon from "@mui/icons-material/Close";
import UndoIcon from "@mui/icons-material/Undo";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import SecurityIcon from "@mui/icons-material/Security";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import { useTranslation } from "react-i18next";

interface ContextualActionBarProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  hasChanges: boolean;
  changeCount: number;
  loading: boolean;
  groupName: string;
  lastSavedAt: Date | null;
  onSave: () => void;
  onDiscard: () => void;
  onUndo: () => void;
  canUndo: boolean;
}

export function ContextualActionBar({
  searchQuery,
  onSearchChange,
  hasChanges,
  changeCount,
  loading,
  groupName,
  lastSavedAt,
  onSave,
  onDiscard,
  onUndo,
  canUndo,
}: ContextualActionBarProps) {
  const { t } = useTranslation();

  const formatTimestamp = (date: Date | null) => {
    if (!date) return t("common.never", "Never");
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return t("common.justNow", "Just now");
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString();
  };

  // Pending changes state
  if (hasChanges) {
    return (
      <Box
        sx={{
          borderBottom: 2,
          borderColor: "warning.main",
          bgcolor: alpha(colorTokens.warning.main, 0.08),
        }}
      >
        <Box
          sx={{
            p: 2,
            display: "flex",
            flexDirection: { xs: "column", sm: "row" },
            gap: 2,
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1.5,
              width: { xs: "100%", sm: "auto" },
            }}
          >
            <Box
              sx={{
                p: 1,
                borderRadius: "50%",
                bgcolor: "warning.light",
                display: "flex",
              }}
            >
              <WarningAmberIcon sx={{ color: "warning.dark", fontSize: 20 }} />
            </Box>

            <Box>
              <Typography variant="subtitle2" fontWeight="bold" color="warning.dark">
                {t("permissions.unsavedChanges", {
                  count: changeCount,
                  group: groupName,
                })}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {t("permissions.unsavedChangesDetail", {
                  count: changeCount,
                  group: groupName,
                  defaultValue: `${changeCount} permission${
                    changeCount !== 1 ? "s" : ""
                  } modified for ${groupName}`,
                })}
              </Typography>
            </Box>
          </Box>

          <Box
            sx={{
              display: "flex",
              gap: 1,
              width: { xs: "100%", sm: "auto" },
              justifyContent: "flex-end",
              flexWrap: "wrap",
            }}
          >
            <Button
              variant="outlined"
              size="small"
              startIcon={<UndoIcon />}
              onClick={onUndo}
              disabled={!canUndo || loading}
              color="inherit"
            >
              {t("common.undo", "Undo")}
            </Button>

            <Button
              variant="outlined"
              size="small"
              startIcon={<CloseIcon />}
              onClick={onDiscard}
              disabled={loading}
              color="error"
            >
              {t("common.discard", "Discard")}
            </Button>

            <Button
              variant="contained"
              size="small"
              startIcon={loading ? <CircularProgress size={16} color="inherit" /> : <SaveIcon />}
              onClick={onSave}
              disabled={loading}
              color="warning"
              sx={{ bgcolor: "warning.main", "&:hover": { bgcolor: "warning.dark" } }}
            >
              {t("common.saveChanges", "Save Changes")}
            </Button>
          </Box>
        </Box>

        {/* Search field stays accessible during edits */}
        <Box
          sx={{
            px: 2,
            pb: 2,
            display: "flex",
            alignItems: "center",
            gap: 1.5,
          }}
        >
          <TextField
            placeholder={t("permissions.filterAreas", "Filter areas...")}
            size="small"
            variant="outlined"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon sx={{ fontSize: 18, color: "text.disabled" }} />
                </InputAdornment>
              ),
            }}
            sx={{ width: { xs: "100%", sm: 256 } }}
          />
        </Box>
      </Box>
    );
  }

  // Default state - no changes
  return (
    <Box
      sx={{
        p: 2,
        borderBottom: 1,
        borderColor: "divider",
        display: "flex",
        flexDirection: { xs: "column", sm: "row" },
        gap: 2,
        justifyContent: "space-between",
        alignItems: "center",
        bgcolor: "background.paper",
      }}
    >
      <Box
        sx={{ display: "flex", alignItems: "center", gap: 2, width: { xs: "100%", sm: "auto" } }}
      >
        <TextField
          placeholder={t("permissions.filterAreas", "Filter areas...")}
          size="small"
          variant="outlined"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon sx={{ fontSize: 18, color: "text.disabled" }} />
              </InputAdornment>
            ),
          }}
          sx={{ width: { xs: "100%", sm: 256 } }}
        />
      </Box>

      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1.5,
          width: { xs: "100%", sm: "auto" },
          justifyContent: "flex-end",
          flexWrap: "wrap",
        }}
      >
        <Chip
          icon={<SecurityIcon sx={{ fontSize: 14 }} />}
          label={groupName}
          size="small"
          color="primary"
          variant="outlined"
        />

        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
          <AccessTimeIcon sx={{ fontSize: 14, color: "text.disabled" }} />
          <Typography variant="caption" color="text.secondary">
            Last saved: {formatTimestamp(lastSavedAt)}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
