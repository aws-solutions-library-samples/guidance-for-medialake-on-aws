import React from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../common/hooks/auth-context";
import { Box, CircularProgress, Typography } from "@mui/material";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const { isAuthenticated, isLoading, isInitialized } = useAuth();

  // Show loading state while authentication is being checked
  if (isLoading || !isInitialized) {
    console.log("ProtectedRoute: Showing loading state", {
      isLoading,
      isInitialized,
    });
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
    console.log(
      "ProtectedRoute: User not authenticated, redirecting to sign-in",
    );
    return <Navigate to="/sign-in" replace />;
  }

  console.log(
    "ProtectedRoute: User authenticated, rendering protected content",
  );
  return <>{children}</>;
};
