import React, { useState } from "react";
import {
  Box,
  Button,
  Container,
  Paper,
  Typography,
  Alert,
} from "@mui/material";
import { S3UploaderModal } from "../features/upload";
import { useFeatureFlag } from "../contexts/FeatureFlagsContext";

const UploadDemo: React.FC = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const isFileUploadEnabled = useFeatureFlag("file-upload-enabled", true);

  const handleOpenModal = () => {
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
  };

  const handleUploadComplete = (files: any[]) => {
    console.log("Upload completed for files:", files);
  };

  // If file upload is disabled, show a message
  if (!isFileUploadEnabled) {
    return (
      <Container maxWidth="lg">
        <Paper sx={{ p: 4, mt: 4 }}>
          <Typography variant="h4" component="h1" gutterBottom>
            S3 Upload System
          </Typography>
          <Alert severity="info" sx={{ mt: 2 }}>
            The file upload feature is currently disabled. Please contact your
            administrator for more information.
          </Alert>
        </Paper>
      </Container>
    );
  }

  return (
    <Container maxWidth="lg">
      <Paper sx={{ p: 4, mt: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          S3 Upload System
        </Typography>
        <Typography variant="body1" paragraph>
          This demo showcases an Uppy-based upload system with dynamic S3
          connector selection and presigned URL generation.
        </Typography>
        <Typography variant="body1" paragraph>
          Features:
        </Typography>
        <Box component="ul">
          <Box component="li">
            <Typography>
              Dynamic S3 connector selection from available connectors
            </Typography>
          </Box>
          <Box component="li">
            <Typography>
              File validation with S3-compatible filename regex
            </Typography>
          </Box>
          <Box component="li">
            <Typography>
              Content type restriction to audio, video, HLS, and MPEG-DASH
            </Typography>
          </Box>
          <Box component="li">
            <Typography>
              Automatic multipart upload for files larger than 100MB
            </Typography>
          </Box>
          <Box component="li">
            <Typography>Support for 5 concurrent uploads</Typography>
          </Box>
        </Box>
        <Box sx={{ mt: 4, textAlign: "center" }}>
          <Button
            variant="contained"
            color="primary"
            size="large"
            onClick={handleOpenModal}
          >
            Open Upload Dialog
          </Button>
        </Box>
      </Paper>

      <S3UploaderModal
        open={isModalOpen}
        onClose={handleCloseModal}
        onUploadComplete={handleUploadComplete}
        title="Upload Media Files"
        description="Select an S3 connector and upload your media files. Only audio, video, HLS, and MPEG-DASH formats are supported."
      />
    </Container>
  );
};

export default UploadDemo;
