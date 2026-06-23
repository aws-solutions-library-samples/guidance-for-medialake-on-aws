import React, { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  LinearProgress,
  Stack,
  Tooltip,
  Typography,
} from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import { useTranslation } from "react-i18next";
import type { UppyFile, Meta, Body } from "@uppy/core";

interface Props {
  files: UppyFile<Meta, Body>[];
  onRemoveFile: (id: string) => void;
  onClearAll: () => void;
}

const statusColor: Record<string, "default" | "info" | "success" | "error"> = {
  queued: "default",
  uploading: "info",
  complete: "success",
  error: "error",
};

function fileStatus(file: UppyFile<Meta, Body>): string {
  if (file.error) return "error";
  if (file.progress?.uploadComplete) return "complete";
  if (file.progress?.uploadStarted) return "uploading";
  return "queued";
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

/**
 * Compact, fully-responsive upload queue.
 *
 * Replaces the previous fixed 6-column MUI Table (Filename/Size/Type/Status/
 * Progress/delete) which overflowed the portal card on narrow screens and
 * forced a horizontal page scroll. Each file is now a single flex row whose
 * name truncates with an ellipsis (full name on hover), with the secondary
 * metadata (size · type) on a caption line, the status chip and remove button
 * pinned to the right, and the upload progress bar spanning the full width
 * below the row while uploading. This layout adapts to any container width, so
 * no column ever pushes the content off-screen.
 */
const UploadQueueTable: React.FC<Props> = ({ files, onRemoveFile, onClearAll }) => {
  const [confirmClear, setConfirmClear] = useState(false);
  const { t } = useTranslation();

  if (files.length === 0) {
    return <Alert severity="info">{t("uploadPortals.queue.noFilesStaged")}</Alert>;
  }

  const totalSize = files.reduce((sum, f) => sum + (f.size || 0), 0);

  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 0.5 }}>
        <Typography variant="body2" color="text.secondary">
          {files.length} file{files.length !== 1 ? "s" : ""} · {formatSize(totalSize)}
        </Typography>
        <Button size="small" color="error" onClick={() => setConfirmClear(true)}>
          {/* i18n-ignore */}
          Clear all
        </Button>
      </Box>

      <Stack
        divider={<Box sx={{ borderBottom: "1px solid", borderColor: "divider" }} />}
        sx={{
          border: "1px solid",
          borderColor: "divider",
          borderRadius: 1,
          overflow: "hidden",
        }}
      >
        {files.map((file) => {
          const status = fileStatus(file);
          const pct =
            file.progress?.bytesTotal && file.progress.bytesTotal > 0
              ? Math.round(((file.progress.bytesUploaded || 0) / file.progress.bytesTotal) * 100)
              : 0;

          return (
            <Box key={file.id} sx={{ px: 1.5, py: 1 }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Tooltip title={file.name} placement="top-start">
                    <Typography variant="body2" noWrap sx={{ fontWeight: 500 }}>
                      {file.name}
                    </Typography>
                  </Tooltip>
                  <Typography variant="caption" color="text.secondary" noWrap component="div">
                    {formatSize(file.size || 0)}
                    {file.type ? ` · ${file.type}` : ""}
                  </Typography>
                </Box>
                <Chip
                  label={status}
                  size="small"
                  color={statusColor[status] || "default"}
                  sx={{ flexShrink: 0 }}
                />
                <IconButton
                  size="small"
                  onClick={() => onRemoveFile(file.id)}
                  aria-label={`Remove ${file.name}`}
                  sx={{ flexShrink: 0 }}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Box>
              {status === "uploading" && (
                <LinearProgress
                  variant="determinate"
                  value={pct}
                  sx={{ mt: 0.75, borderRadius: 1, height: 4 }}
                />
              )}
            </Box>
          );
        })}
      </Stack>

      <Dialog open={confirmClear} onClose={() => setConfirmClear(false)}>
        <DialogTitle>Clear all files?</DialogTitle>
        <DialogContent>
          <Typography>{t("uploadPortals.queue.clearAllConfirm")}</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirmClear(false)}>Cancel</Button>
          <Button
            color="error"
            onClick={() => {
              setConfirmClear(false);
              onClearAll();
            }}
          >
            {/* i18n-ignore */}
            Clear all
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default UploadQueueTable;
