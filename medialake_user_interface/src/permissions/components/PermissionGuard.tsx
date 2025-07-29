// src/permissions/components/PermissionGuard.tsx
import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { usePermission } from "../hooks/usePermission";
import { useAuth } from "../../common/hooks/auth-context";
import { Actions, Subjects } from "../types/ability.types";
import { PermissionGuardProps } from "../types/permission.types";
import { Box, CircularProgress, Typography } from "@mui/material";

/**
 * Higher-order component for protecting routes based on permissions
 *
 * @param props Component props
 * @returns React element or redirect
 */
export function PermissionGuard({
  action,
  subject,
  field,
  fallback = null,
  children,
}: PermissionGuardProps) {
  const { can, loading } = usePermission();
  const { isAuthenticated, isLoading: authLoading, isInitialized } = useAuth();
  const location = useLocation();

  // Show loading state if authentication or permissions are still loading/initializing
  if (authLoading || !isInitialized || loading) {
    console.log("PermissionGuard: Showing loading state", {
      authLoading,
      isInitialized,
      permissionLoading: loading,
      currentPath: location.pathname,
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
          Loading permissions...
        </Typography>
      </Box>
    );
  }

  // If not authenticated after initialization, redirect to sign-in
  if (isInitialized && !isAuthenticated) {
    console.log(
      "PermissionGuard: User not authenticated, redirecting to sign-in",
    );
    return <Navigate to="/sign-in" state={{ from: location }} replace />;
  }

  // Check if the user has permission
  console.log(
    "🔒 PermissionGuard: Starting permission check for route:",
    location.pathname,
  );
  console.log("🔒 Required permission:", { action, subject, field });
  console.log("🔒 Auth state:", {
    isAuthenticated,
    isInitialized,
    authLoading,
  });
  console.log("🔒 Permission loading:", loading);

  const allowed = can(action, subject, field);
  console.log("🔒 PermissionGuard: Final permission result:", allowed);

  // If allowed, render the children
  if (allowed) {
    console.log("🔒 PermissionGuard: Access GRANTED for", location.pathname);
    return <>{children}</>;
  }

  // If fallback is provided, render it
  if (fallback) {
    console.log(
      "🔒 PermissionGuard: Using fallback component for",
      location.pathname,
    );
    return <>{fallback}</>;
  }

  // Otherwise, redirect to the login page or access denied page
  console.log("🔒 PermissionGuard: Access DENIED for", location.pathname);
  console.log("🔒 Required permission was:", { action, subject, field });
  console.log("🔒 Redirecting to /access-denied");
  return <Navigate to="/access-denied" state={{ from: location }} replace />;
}

/**
 * Higher-order component for creating a route guard
 *
 * @param action The action to check
 * @param subject The subject to check
 * @param field Optional field to check
 * @returns A function that takes a component and returns a guarded component
 */
export function withPermission(
  action: Actions,
  subject: Subjects,
  field?: string,
) {
  return function (Component: React.ComponentType<any>) {
    return function WithPermissionComponent(props: any) {
      return (
        <PermissionGuard action={action} subject={subject} field={field}>
          <Component {...props} />
        </PermissionGuard>
      );
    };
  };
}

/**
 * Component for protecting routes in a router configuration
 *
 * @param props Component props
 * @returns React element or null
 */
export function RoutePermissionGuard({
  permission,
  element,
}: {
  permission: { action: Actions; subject: Subjects; field?: string };
  element: React.ReactNode;
}) {
  const location = useLocation();

  console.log(
    "🛡️  RoutePermissionGuard: Protecting route",
    location.pathname,
    "with permission:",
    permission,
  );

  return (
    <PermissionGuard
      action={permission.action}
      subject={permission.subject}
      field={permission.field}
    >
      {element}
    </PermissionGuard>
  );
}
