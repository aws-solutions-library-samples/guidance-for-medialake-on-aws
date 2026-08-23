import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router";
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

  /**
   * Whether there is an in-app history entry behind this one.
   *
   * React Router tracks its index into the session history on
   * `window.history.state.idx`. An index of 0 means this page is the first entry
   * in the session, so `navigate(-1)` would leave the app entirely rather than
   * return to it — which happens on a deep link into a guarded route, a link
   * opened from another app, a fresh tab, or a refresh while already here.
   * Denials redirect with `replace`, so the route that was denied is overwritten
   * rather than left behind, making index 0 a normal occurrence.
   *
   * A missing or non-numeric index is treated as "no history" so the fallback
   * keeps the user inside the app.
   */
  const canGoBackInApp = (): boolean => {
    const index = (window.history.state as { idx?: number } | null)?.idx;
    return typeof index === "number" && index > 0;
  };

  // Replace so this page leaves the history stack — otherwise a single press of
  // browser Back lands the user right back on the access-denied screen.
  const handleGoHome = () => {
    navigate("/", { replace: true });
  };

  const handleGoBack = () => {
    if (canGoBackInApp()) {
      navigate(-1);
    } else {
      handleGoHome();
    }
  };

  return (
    <Container maxWidth="md" sx={{ mt: 8 }}>
      <Paper
        elevation={0}
        sx={{
          p: 4,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          borderRadius: 3,
          border: "1px solid",
          borderColor: "divider",
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
