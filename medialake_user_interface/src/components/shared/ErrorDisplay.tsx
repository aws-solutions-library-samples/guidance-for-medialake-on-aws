import React from "react";
import { Box, Paper, Typography, Alert, AlertTitle } from "@mui/material";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";

interface ErrorDisplayProps {
  title: string;
  message: string;
  detailedMessage?: string;
}

const ErrorDisplay: React.FC<ErrorDisplayProps> = ({
  title,
  message,
  detailedMessage,
}) => {
  return (
    <Box sx={{ mt: 4 }}>
      <Paper
        elevation={0}
        sx={{
          p: 4,
          borderRadius: 2,
          bgcolor: "background.paper",
          border: (theme) => `1px solid ${theme.palette.divider}`,
        }}
      >
        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            textAlign: "center",
            mb: 3,
          }}
        >
          <ErrorOutlineIcon color="error" sx={{ fontSize: 64, mb: 2 }} />
          <Typography variant="h5" gutterBottom>
            {title}
          </Typography>
          <Typography variant="body1" color="text.secondary">
            {message}
          </Typography>
        </Box>

        {detailedMessage && (
          <Alert severity="error" sx={{ mt: 2 }}>
            <AlertTitle>Error Details</AlertTitle>
            {detailedMessage}
          </Alert>
        )}
      </Paper>
    </Box>
  );
};

export default ErrorDisplay;
