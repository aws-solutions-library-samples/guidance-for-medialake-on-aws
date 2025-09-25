import React, { useState } from "react";
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Box,
} from "@mui/material";
import FileUploader from "./FileUploader";

interface S3UploaderModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  path?: string;
  onUploadComplete?: (files: any[]) => void;
}

const S3UploaderModal: React.FC<S3UploaderModalProps> = ({
  open,
  onClose,
  title = "Upload Files",
  description = "Select an S3 connector and upload your files",
  path = "",
  onUploadComplete,
}) => {
  const [uploadedFiles, setUploadedFiles] = useState<any[]>([]);

  const handleUploadComplete = (files: any[]) => {
    setUploadedFiles(files);
    if (onUploadComplete) {
      onUploadComplete(files);
    }
  };

  const handleClose = () => {
    setUploadedFiles([]);
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
      <DialogTitle>{title}</DialogTitle>
      <DialogContent>
        <DialogContentText>{description}</DialogContentText>
        <Box sx={{ mt: 2 }}>
          <FileUploader onUploadComplete={handleUploadComplete} path={path} />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>Close</Button>
      </DialogActions>
    </Dialog>
  );
};

export default S3UploaderModal;
