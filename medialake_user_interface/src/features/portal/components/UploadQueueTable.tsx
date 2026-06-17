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
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
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

const UploadQueueTable: React.FC<Props> = ({ files, onRemoveFile, onClearAll }) => {
  const [confirmClear, setConfirmClear] = useState(false);
  const { t } = useTranslation();

  if (files.length === 0) {
    return <Alert severity="info">{t("uploadPortals.queue.noFilesStaged")}</Alert>;
  }

  const totalSize = files.reduce((sum, f) => sum + (f.size || 0), 0);

  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 1 }}>
        <Typography variant="body2" color="text.secondary">
          {files.length} file{files.length !== 1 ? "s" : ""} · {formatSize(totalSize)}
        </Typography>
        <Button size="small" color="error" onClick={() => setConfirmClear(true)}>
          Clear All
        </Button>
      </Box>

      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Filename</TableCell>
              <TableCell>Size</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Progress</TableCell>
              <TableCell />
            </TableRow>
          </TableHead>
          <TableBody>
            {files.map((file) => {
              const status = fileStatus(file);
              const pct =
                file.progress?.bytesTotal && file.progress.bytesTotal > 0
                  ? Math.round(
                      ((file.progress.bytesUploaded || 0) / file.progress.bytesTotal) * 100
                    )
                  : 0;

              return (
                <TableRow key={file.id}>
                  <TableCell
                    sx={{
                      maxWidth: 200,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {file.name}
                  </TableCell>
                  <TableCell>{formatSize(file.size || 0)}</TableCell>
                  <TableCell>{file.type || "—"}</TableCell>
                  <TableCell>
                    <Chip label={status} size="small" color={statusColor[status] || "default"} />
                  </TableCell>
                  <TableCell sx={{ minWidth: 100 }}>
                    {status === "uploading" && <LinearProgress variant="determinate" value={pct} />}
                  </TableCell>
                  <TableCell>
                    <IconButton size="small" onClick={() => onRemoveFile(file.id)}>
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>

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
            Clear All
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default UploadQueueTable;
