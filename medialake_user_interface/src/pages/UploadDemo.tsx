import React, { useState } from "react";
import { Box, Button, Container, Paper, Typography } from "@mui/material";
import { S3UploaderModal } from "../features/upload";

const UploadDemo: React.FC = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);

  const handleOpenModal = () => {
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
  };

  const handleUploadComplete = (files: any[]) => {
    console.log("Upload completed for files:", files);
  };

  return (
    <Container maxWidth="lg">
      <Paper sx={{ p: 4, mt: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          S3 Upload System
        </Typography>
        <Typography variant="body1" paragraph>
          This demo showcases an Uppy 5.0 with unified Dashboard experience and
          built-in progress tracking for dynamic S3 connector selection and
          presigned URL generation.
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
              Content type restriction to audio/*, video/*, image/*, HLS, and
              MPEG-DASH
            </Typography>
          </Box>
          <Box component="li">
            <Typography>
              Automatic multipart upload for files larger than 100MB with
              dynamic part size (5MB default, auto-adjusts for files exceeding
              10,000 parts)
            </Typography>
          </Box>
          <Box component="li">
            <Typography>Support for 5 concurrent uploads</Typography>
          </Box>
          <Box component="li">
            <Typography>
              Built-in progress UI with upload status, speed, and ETA (powered
              by Uppy 5.0 Dashboard)
            </Typography>
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
        description="Select an S3 connector and upload your media files. Files larger than 100MB will automatically use multipart upload with on-demand part signing. Only audio/*, video/*, image/*, HLS, and MPEG-DASH formats are supported."
      />
    </Container>
  );
};

export default UploadDemo;
