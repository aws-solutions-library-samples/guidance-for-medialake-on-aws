import React from "react";
import { Navigate, useLocation } from "react-router";
import { useAuth } from "../common/hooks/auth-context";
import { Box, CircularProgress, Typography } from "@mui/material";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated, isLoading, isInitialized } = useAuth();
  const location = useLocation();

  // Show loading state while authentication is being checked
  if (isLoading || !isInitialized) {
    return (
      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          height: "100vh",
          gap: 2,
        }}
      >
        <CircularProgress />
        <Typography variant="body2" color="text.secondary">
          Checking authentication...
        </Typography>
      </Box>
    );
  }

  // Only redirect to sign-in after we've confirmed the user is not authenticated
  if (isInitialized && !isAuthenticated) {
    // Remember where the user was going so AuthPage can return them there.
    return <Navigate to="/sign-in" state={{ from: location }} replace />;
  }

  return <>{children}</>;
};
