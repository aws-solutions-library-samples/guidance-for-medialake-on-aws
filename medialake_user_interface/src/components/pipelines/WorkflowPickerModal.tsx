import React, { useEffect, useMemo, useState } from "react";
import {
  Dialog,
  DialogContent,
  Box,
  Typography,
  CircularProgress,
  IconButton,
  InputBase,
  alpha,
  useTheme,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import SearchIcon from "@mui/icons-material/Search";
import AccountTreeOutlinedIcon from "@mui/icons-material/AccountTreeOutlined";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import CheckIcon from "@mui/icons-material/Check";
import LayersClearOutlinedIcon from "@mui/icons-material/LayersClearOutlined";
import { useTranslation } from "react-i18next";
import { accentColor } from "@/theme/accessibleAccent";

/**
 * Minimal shape the picker needs from a pipeline. Deliberately narrower than
 * `Pipeline` from the pipelines feature: the batch sidebar passes objects that
 * came back from `GET /pipelines`, whose runtime shape carries `definition`
 * rather than the declared `configuration`. Narrowing here keeps the modal
 * decoupled from that discrepancy.
 */
export interface WorkflowPickerItem {
  id: string;
  name: string;
  description?: string;
  createdAt?: string;
}

interface WorkflowPickerModalProps {
  open: boolean;
  onClose: () => void;
  /** Workflows eligible for the current selection (already type-filtered). */
  workflows: WorkflowPickerItem[];
  isLoading?: boolean;
  /** How many assets the workflow will run against — shown in the subtitle. */
  selectedCount: number;
  onRun: (workflow: WorkflowPickerItem) => void;
  isRunning?: boolean;
}

/**
 * Full list of workflows that can run against the current selection, with
 * search. Opened from the Workflow button in the selection bin; the bin's
 * dropdown covers the "most recent" shortcut, this covers "show me everything".
 */
export const WorkflowPickerModal: React.FC<WorkflowPickerModalProps> = ({
  open,
  onClose,
  workflows,
  isLoading = false,
  selectedCount,
  onRun,
  isRunning = false,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";
  // primary.main only reaches 2.68:1 on the dark paper, so it is unreadable as
  // text and below the 3:1 UI threshold for icons and focus rings. Tints keep
  // using primary.main -- they sit behind content rather than being read.
  const accent = accentColor(theme, "primary");

  const [searchQuery, setSearchQuery] = useState("");
  const [selectedId, setSelectedId] = useState("");

  // Reset transient state each time the modal opens so a previous search or
  // selection never carries over into a new invocation.
  useEffect(() => {
    if (open) {
      setSearchQuery("");
      setSelectedId("");
    }
  }, [open]);

  // Newest first — matches how the bin's dropdown surfaces "recently created".
  const sorted = useMemo(
    () =>
      [...workflows].sort((a, b) => {
        const aTime = a.createdAt ? Date.parse(a.createdAt) : NaN;
        const bTime = b.createdAt ? Date.parse(b.createdAt) : NaN;
        if (Number.isNaN(aTime) && Number.isNaN(bTime)) return a.name.localeCompare(b.name);
        if (Number.isNaN(aTime)) return 1;
        if (Number.isNaN(bTime)) return -1;
        return bTime - aTime;
      }),
    [workflows]
  );

  const filtered = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    if (!query) return sorted;
    return sorted.filter(
      (w) =>
        w.name.toLowerCase().includes(query) || (w.description ?? "").toLowerCase().includes(query)
    );
  }, [sorted, searchQuery]);

  const selected = workflows.find((w) => w.id === selectedId);

  const formatCreated = (createdAt?: string): string | null => {
    if (!createdAt) return null;
    const parsed = Date.parse(createdAt);
    if (Number.isNaN(parsed)) return null;
    return t("common.batchOperations.workflowPicker.created", "Created {{date}}", {
      date: new Date(parsed).toLocaleDateString(),
    });
  };

  const handleClose = () => {
    if (!isRunning) onClose();
  };

  const handleRun = () => {
    if (selected && !isRunning) onRun(selected);
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      slotProps={{
        paper: {
          sx: {
            borderRadius: 3,
            bgcolor: "background.paper",
            backgroundImage: "none",
            overflow: "hidden",
            maxHeight: "80vh",
          },
        },
      }}
    >
      {/* Header */}
      <Box
        sx={{
          px: 3,
          pt: 2.5,
          pb: 2,
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          borderBottom: `1px solid ${alpha(theme.palette.divider, 0.08)}`,
        }}
      >
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography
            variant="h6"
            sx={{ fontWeight: 700, fontSize: "1.1rem", letterSpacing: "-0.01em", lineHeight: 1.3 }}
          >
            {t("common.batchOperations.workflowPicker.title", "Run Workflow")}
          </Typography>
          <Typography variant="body2" sx={{ color: "text.secondary", mt: 0.3, fontSize: "0.8rem" }}>
            {t("common.batchOperations.itemsSelected", "{{count}} selected", {
              count: selectedCount,
            })}
          </Typography>
        </Box>
        <IconButton
          onClick={handleClose}
          disabled={isRunning}
          size="small"
          sx={{
            color: "text.secondary",
            mt: -0.5,
            mr: -0.5,
            "&:hover": { bgcolor: alpha(theme.palette.text.secondary, 0.08) },
          }}
          aria-label={t("common.close", "Close")}
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>

      <DialogContent sx={{ p: 0, display: "flex", flexDirection: "column" }}>
        {/* Search */}
        <Box sx={{ px: 2.5, pt: 2, pb: 1.5 }}>
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1,
              px: 1.5,
              py: 0.6,
              borderRadius: 2,
              bgcolor: alpha(theme.palette.text.primary, isDark ? 0.06 : 0.04),
              border: `1px solid ${alpha(theme.palette.divider, 0.12)}`,
              transition: "border-color 0.2s, box-shadow 0.2s",
              "&:focus-within": {
                borderColor: accent,
                boxShadow: `0 0 0 2px ${alpha(accent, 0.3)}`,
              },
            }}
          >
            <SearchIcon sx={{ fontSize: 20, color: "text.secondary", flexShrink: 0 }} />
            <InputBase
              placeholder={t("common.batchOperations.workflowPicker.search", "Search workflows...")}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              sx={{
                flex: 1,
                fontSize: "0.85rem",
                "& input": { py: 0.4 },
                "& input::placeholder": { color: "text.secondary", opacity: 0.7 },
              }}
              inputProps={{
                "aria-label": t(
                  "common.batchOperations.workflowPicker.search",
                  "Search workflows..."
                ),
              }}
            />
            {searchQuery && (
              <IconButton
                size="small"
                onClick={() => setSearchQuery("")}
                sx={{ p: 0.3 }}
                aria-label={t("common.clear", "Clear")}
              >
                <CloseIcon sx={{ fontSize: 16 }} />
              </IconButton>
            )}
          </Box>
        </Box>

        {/* List */}
        <Box sx={{ flex: 1, overflowY: "auto", px: 2.5, pb: 1, minHeight: 200, maxHeight: 340 }}>
          {isLoading ? (
            <Box sx={{ display: "flex", justifyContent: "center", alignItems: "center", py: 6 }}>
              <CircularProgress size={28} />
            </Box>
          ) : filtered.length === 0 ? (
            <Box sx={{ textAlign: "center", py: 5, px: 2 }}>
              <LayersClearOutlinedIcon
                sx={{ fontSize: 44, color: alpha(theme.palette.text.secondary, 0.3), mb: 1.5 }}
              />
              <Typography variant="body2" sx={{ color: "text.secondary", fontWeight: 500 }}>
                {searchQuery
                  ? t(
                      "common.batchOperations.workflowPicker.noResults",
                      "No workflows match your search"
                    )
                  : t(
                      "common.batchOperations.noPipelinesAvailable",
                      "No manual pipelines available for selected asset types"
                    )}
              </Typography>
            </Box>
          ) : (
            <Box sx={{ display: "flex", flexDirection: "column", gap: 0.5 }}>
              {filtered.map((workflow) => {
                const isSelected = selectedId === workflow.id;
                const created = formatCreated(workflow.createdAt);

                return (
                  <Box
                    key={workflow.id}
                    onClick={() => setSelectedId(workflow.id)}
                    role="option"
                    aria-selected={isSelected}
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setSelectedId(workflow.id);
                      }
                    }}
                    sx={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: 1.5,
                      px: 1.5,
                      py: 1.2,
                      borderRadius: 2,
                      cursor: "pointer",
                      transition: "background-color 0.15s ease",
                      border: `1.5px solid ${isSelected ? alpha(accent, 0.6) : "transparent"}`,
                      bgcolor: isSelected
                        ? alpha(theme.palette.primary.main, isDark ? 0.1 : 0.06)
                        : "transparent",
                      "&:hover": {
                        bgcolor: isSelected
                          ? alpha(theme.palette.primary.main, isDark ? 0.14 : 0.08)
                          : alpha(theme.palette.text.primary, isDark ? 0.05 : 0.03),
                      },
                    }}
                  >
                    <Box
                      sx={{
                        mt: 0.2,
                        width: 32,
                        height: 32,
                        borderRadius: 1.5,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        bgcolor: isSelected
                          ? alpha(theme.palette.primary.main, isDark ? 0.2 : 0.12)
                          : alpha(theme.palette.text.primary, isDark ? 0.06 : 0.05),
                        flexShrink: 0,
                      }}
                    >
                      {isSelected ? (
                        <CheckIcon sx={{ fontSize: 18, color: accent }} />
                      ) : (
                        <AccountTreeOutlinedIcon sx={{ fontSize: 18, color: accent }} />
                      )}
                    </Box>

                    <Box sx={{ flex: 1, minWidth: 0 }}>
                      <Typography
                        variant="body2"
                        sx={{
                          fontWeight: isSelected ? 600 : 500,
                          fontSize: "0.85rem",
                          lineHeight: 1.3,
                          color: isSelected ? accent : "text.primary",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {workflow.name}
                      </Typography>
                      {workflow.description && (
                        <Typography
                          variant="caption"
                          sx={{
                            color: "text.secondary",
                            fontSize: "0.72rem",
                            display: "block",
                            mt: 0.2,
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {workflow.description}
                        </Typography>
                      )}
                      {created && (
                        <Typography
                          variant="caption"
                          sx={{
                            color: "text.secondary",
                            fontSize: "0.7rem",
                            opacity: 0.7,
                            display: "block",
                            mt: 0.1,
                          }}
                        >
                          {created}
                        </Typography>
                      )}
                    </Box>
                  </Box>
                );
              })}
            </Box>
          )}
        </Box>

        {/* Footer */}
        <Box
          sx={{
            px: 2.5,
            py: 2,
            borderTop: `1px solid ${alpha(theme.palette.divider, 0.08)}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end",
            gap: 1.5,
          }}
        >
          <Box
            component="button"
            onClick={handleClose}
            disabled={isRunning}
            sx={{
              px: 2.5,
              py: 0.9,
              border: "none",
              borderRadius: 1.5,
              bgcolor: "transparent",
              color: "text.secondary",
              fontSize: "0.82rem",
              fontWeight: 500,
              cursor: "pointer",
              "&:hover": { bgcolor: alpha(theme.palette.text.primary, 0.06) },
              "&:disabled": { opacity: 0.5, cursor: "default" },
            }}
          >
            {t("common.cancel", "Cancel")}
          </Box>
          <Box
            component="button"
            onClick={handleRun}
            disabled={!selectedId || isRunning}
            data-testid="workflow-picker-run"
            sx={{
              px: 3,
              py: 0.9,
              border: "none",
              borderRadius: 1.5,
              bgcolor: "primary.main",
              color: "primary.contrastText",
              fontSize: "0.82rem",
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 0.7,
              transition: "background-color 0.15s ease, opacity 0.15s ease",
              "&:hover": { bgcolor: "primary.dark" },
              "&:disabled": { opacity: 0.4, cursor: "default" },
            }}
          >
            {isRunning ? (
              <CircularProgress size={16} color="inherit" />
            ) : (
              <PlayArrowRoundedIcon sx={{ fontSize: 18 }} />
            )}
            {t("common.batchOperations.workflowPicker.run", "Run")}
          </Box>
        </Box>
      </DialogContent>
    </Dialog>
  );
};

export default WorkflowPickerModal;
