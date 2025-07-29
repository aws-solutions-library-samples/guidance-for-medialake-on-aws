import React, { useState, useCallback } from "react";
import { Box, Typography, Button, Paper, Alert, Stack } from "@mui/material";
import { ErrorBoundary as ReactErrorBoundary } from "react-error-boundary";
import { useTranslation } from "react-i18next";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallbackRender?: (props: {
    error: Error;
    resetErrorBoundary: () => void;
  }) => React.ReactNode;
  onReset?: () => void;
  onError?: (error: Error, info: { componentStack: string }) => void;
}

interface FallbackProps {
  error: Error;
  resetErrorBoundary: () => void;
}

const DefaultFallback: React.FC<FallbackProps> = ({
  error,
  resetErrorBoundary,
}) => {
  const { t } = useTranslation();
  const [showDetails, setShowDetails] = useState(false);

  return (
    <Paper
      elevation={1}
      sx={{
        p: 3,
        borderRadius: 2,
        borderLeft: "4px solid",
        borderColor: "error.main",
        width: "100%",
        mb: 2,
      }}
    >
      <Stack spacing={2}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
          <ErrorOutlineIcon color="error" />
          <Typography variant="h6">
            {t("errors.componentError", "Component Error")}
          </Typography>
        </Box>

        <Typography variant="body2" color="text.secondary">
          {t(
            "errors.componentErrorMessage",
            "An error occurred in this component. You can try resetting it.",
          )}
        </Typography>

        <Box>
          <Button
            variant="text"
            size="small"
            color="primary"
            onClick={() => setShowDetails(!showDetails)}
            sx={{ mb: 1 }}
          >
            {showDetails
              ? t("errors.hideDetails", "Hide Details")
              : t("errors.showDetails", "Show Details")}
          </Button>

          {showDetails && (
            <Alert severity="error" sx={{ mb: 2 }}>
              <pre
                style={{
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  margin: 0,
                  fontSize: "0.875rem",
                }}
              >
                {error.message}
                {error.stack ? `\n\n${error.stack}` : ""}
              </pre>
            </Alert>
          )}
        </Box>

        <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 1 }}>
          <Button
            variant="outlined"
            size="small"
            onClick={() => window.location.reload()}
          >
            {t("errors.refreshPage", "Refresh Page")}
          </Button>
          <Button variant="contained" size="small" onClick={resetErrorBoundary}>
            {t("errors.tryAgain", "Try Again")}
          </Button>
        </Box>
      </Stack>
    </Paper>
  );
};

export const ErrorBoundary: React.FC<ErrorBoundaryProps> = ({
  children,
  fallbackRender,
  onReset,
  onError,
}) => {
  // Log the error to the console by default
  const handleError = useCallback(
    (error: Error, info: { componentStack: string }) => {
      console.error("Caught an error:", error, info);
      onError?.(error, info);
    },
    [onError],
  );

  return (
    <ReactErrorBoundary
      fallbackRender={
        fallbackRender || ((props) => <DefaultFallback {...props} />)
      }
      onReset={onReset}
      onError={handleError}
    >
      {children}
    </ReactErrorBoundary>
  );
};
