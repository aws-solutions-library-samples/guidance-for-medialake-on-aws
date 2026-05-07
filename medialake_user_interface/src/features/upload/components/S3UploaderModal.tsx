import React, { useState, useEffect } from "react";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Typography,
} from "@mui/material";
import FolderIcon from "@mui/icons-material/Folder";
import { useTranslation } from "react-i18next";
import FileUploader from "./FileUploader";

/**
 * S3UploaderModalProps interface
 * @param path - Initial upload path for the uploader
 */
interface S3UploaderModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  path?: string;
  onUploadComplete?: (files: any[]) => void;
  onUploadError?: (error: Error, file: any) => void;
}

const S3UploaderModal: React.FC<S3UploaderModalProps> = ({
  open,
  onClose,
  title,
  description,
  path = "",
  onUploadComplete,
  onUploadError,
}) => {
  const { t } = useTranslation();
  const [, setUploadedFiles] = useState<any[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [currentPath, setCurrentPath] = useState<string>(path || "");

  // Sync currentPath with path prop
  useEffect(() => {
    setCurrentPath(path || "");
  }, [path]);

  const handleUploadComplete = (files: any[]) => {
    setUploadedFiles(files);
    setUploadError(null);
    if (onUploadComplete) {
      onUploadComplete(files);
    }
  };

  const handleUploadError = (error: Error, file: any) => {
    const errorMessage = `Failed to upload ${file.name}: ${error.message}`;
    console.error(errorMessage, { error, file });
    setUploadError(errorMessage);
    if (onUploadError) {
      onUploadError(error, file);
    }
  };

  const handleClose = () => {
    setUploadedFiles([]);
    setUploadError(null);
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>{title || t("upload.title")}</DialogTitle>
      <DialogContent>
        <DialogContentText>{description}</DialogContentText>
        {currentPath && (
          <Alert severity="info" sx={{ mt: 2, mb: 2 }} icon={<FolderIcon />}>
            <Typography variant="body2">
              <strong>{t("upload.uploadingTo")}:</strong> {currentPath || "/"}
            </Typography>
          </Alert>
        )}
        {uploadError && (
          <Alert severity="error" sx={{ mt: 2, mb: 2 }}>
            {uploadError}
          </Alert>
        )}
        <Box sx={{ mt: 2 }}>
          <FileUploader
            onUploadComplete={handleUploadComplete}
            onUploadError={handleUploadError}
            path={path}
            onPathChange={(p) => setCurrentPath(p)}
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>{t("common.close")}</Button>
      </DialogActions>
    </Dialog>
  );
};

export default S3UploaderModal;
