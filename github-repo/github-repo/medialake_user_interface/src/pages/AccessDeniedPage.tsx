import React from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Box, Typography, Button, Container, Paper } from "@mui/material";
import LockIcon from "@mui/icons-material/Lock";

/**
 * Access Denied Page
 *
 * This page is displayed when a user tries to access a route they don't have permission for.
 * It provides a clear message and a button to go back to the home page.
 */
const AccessDeniedPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || "/";

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

        <Typography
          variant="body1"
          color="text.secondary"
          align="center"
          sx={{ mb: 4 }}
        >
          You don't have permission to access this page. Please contact your
          administrator if you believe this is an error.
        </Typography>

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
