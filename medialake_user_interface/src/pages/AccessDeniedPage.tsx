import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Box, Typography, Button, Container, Paper, Alert } from "@mui/material";
import LockIcon from "@mui/icons-material/Lock";

interface AccessDeniedError {
  message: string;
  requiredPermission?: string;
  attemptedUrl?: string;
  timestamp?: string;
}

/**
 * Access Denied Page
 *
 * This page is displayed when a user tries to access a route they don't have permission for.
 * It provides a clear message and a button to go back to the home page.
 *
 * Error details are retrieved from sessionStorage if available (set by API interceptor).
 */
const AccessDeniedPage: React.FC = () => {
  const navigate = useNavigate();
  const [errorDetails, setErrorDetails] = useState<AccessDeniedError | null>(null);

  useEffect(() => {
    // Try to get error details from sessionStorage
    const storedError = sessionStorage.getItem("accessDeniedError");
    if (storedError) {
      try {
        const parsed = JSON.parse(storedError);
        setErrorDetails(parsed);
        // Clear the error from sessionStorage after reading
        sessionStorage.removeItem("accessDeniedError");
      } catch (e) {
        console.error("Failed to parse access denied error:", e);
      }
    }
  }, []);

  const handleGoBack = () => {
    navigate(-1);
  };

  const handleGoHome = () => {
    navigate("/");
  };

  return (
    <Container maxWidth="md" sx={{ mt: 8 }}>
      <Paper
        elevation={3}
        sx={{
          p: 4,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          borderRadius: 2,
        }}
      >
        <LockIcon color="error" sx={{ fontSize: 64, mb: 2 }} />

        <Typography variant="h4" component="h1" gutterBottom>
          Access Denied
        </Typography>

        {errorDetails ? (
          <>
            <Alert severity="error" sx={{ mb: 3, width: "100%" }}>
              <Typography variant="body1" sx={{ mb: 1 }}>
                {errorDetails.message}
              </Typography>
              {errorDetails.requiredPermission && (
                <Typography variant="body2" color="text.secondary">
                  Required permission: <strong>{errorDetails.requiredPermission}</strong>
                </Typography>
              )}
            </Alert>

            <Typography variant="body2" color="text.secondary" align="center" sx={{ mb: 4 }}>
              Please contact your administrator if you need access to this feature.
            </Typography>
          </>
        ) : (
          <Typography variant="body1" color="text.secondary" align="center" sx={{ mb: 4 }}>
            You don't have permission to access this page. Please contact your administrator if you
            believe this is an error.
          </Typography>
        )}

        <Box sx={{ display: "flex", gap: 2 }}>
          <Button variant="outlined" onClick={handleGoBack}>
            Go Back
          </Button>
          <Button variant="contained" onClick={handleGoHome}>
            Go to Home
          </Button>
        </Box>
      </Paper>
    </Container>
  );
};

export default AccessDeniedPage;
