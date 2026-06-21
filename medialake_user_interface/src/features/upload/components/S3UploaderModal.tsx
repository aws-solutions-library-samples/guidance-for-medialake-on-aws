import React, { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
} from "@mui/material";
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
  defaultConnectorId?: string;
  lockConnector?: boolean;
  defaultObjectPrefix?: string;
}

const S3UploaderModal: React.FC<S3UploaderModalProps> = ({
  open,
  onClose,
  title,
  description,
  path = "",
  onUploadComplete,
  onUploadError,
  defaultConnectorId,
  lockConnector,
  defaultObjectPrefix,
}) => {
  const { t } = useTranslation();
  const [, setUploadedFiles] = useState<any[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);

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
            defaultConnectorId={defaultConnectorId}
            lockConnector={lockConnector}
            defaultObjectPrefix={defaultObjectPrefix}
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
