import React from "react";
import { Box, Typography, Button, Paper, Divider } from "@mui/material";
import {
  useRouteError,
  useNavigate,
  isRouteErrorResponse,
} from "react-router-dom";
import { useTranslation } from "react-i18next";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";

const RouteErrorBoundary: React.FC = () => {
  const error = useRouteError();
  const navigate = useNavigate();
  const { t } = useTranslation();

  let errorMessage = "";
  let statusText = "";
  let errorStatusCode = 0;

  if (isRouteErrorResponse(error)) {
    // This is a route error response from React Router
    errorStatusCode = error.status;
    statusText = error.statusText;
    errorMessage = error.data?.message || error.data;
  } else if (error instanceof Error) {
    // This is a JavaScript Error object
    errorMessage = error.message;
    statusText = error.name;
  } else if (typeof error === "string") {
    // Just a string message
    errorMessage = error;
  } else {
    // Unknown error type
    errorMessage = "An unexpected error occurred";
  }

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: "100vh",
        p: 3,
      }}
    >
      <Paper
        elevation={3}
        sx={{
          p: 4,
          maxWidth: 600,
          width: "100%",
          borderRadius: 2,
        }}
      >
        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 2,
            mb: 3,
          }}
        >
          <ErrorOutlineIcon color="error" sx={{ fontSize: 64 }} />

          {errorStatusCode ? (
            <Typography variant="h3" fontWeight="bold">
              {errorStatusCode}
            </Typography>
          ) : null}

          <Typography variant="h5" fontWeight="medium" textAlign="center">
            {statusText ||
              t("errors.somethingWentWrong", "Something went wrong")}
          </Typography>
        </Box>

        <Divider sx={{ my: 2 }} />

        <Typography
          variant="body1"
          color="text.secondary"
          sx={{ mb: 3 }}
          textAlign="center"
        >
          {errorMessage}
        </Typography>

        <Box sx={{ display: "flex", justifyContent: "center", gap: 2 }}>
          <Button variant="outlined" onClick={() => window.location.reload()}>
            {t("errors.refreshPage", "Refresh Page")}
          </Button>
          <Button
            variant="contained"
            color="primary"
            onClick={() => navigate("/")}
          >
            {t("errors.goToHomepage", "Go to Homepage")}
          </Button>
        </Box>
      </Paper>
    </Box>
  );
};

export default RouteErrorBoundary;
