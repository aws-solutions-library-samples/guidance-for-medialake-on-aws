// src/permissions/components/Can.tsx
import React, { useState, useEffect } from "react";
import { usePermission } from "../hooks/usePermission";
import { useAuth } from "../../common/hooks/auth-context";
import { CanProps } from "../types/permission.types";
import { Actions, Subjects } from "../types/ability.types";

/**
 * Component for conditional rendering based on permissions
 *
 * @param props Component props
 * @returns React element or null
 */
export function Can({
  I: action,
  a: subject,
  field,
  passThrough = false,
  children,
}: CanProps) {
  const { can, loading } = usePermission();
  const { isAuthenticated, isInitialized } = useAuth();
  const [lastKnownResult, setLastKnownResult] = useState<boolean | null>(null);

  // Don't do permission checks until we're authenticated and initialized
  if (!isAuthenticated || !isInitialized) {
    return null;
  }

  // Calculate allowed value (always call hooks first)
  const allowed = can(action as Actions, subject as Subjects, field);

  // Update last known result (always call useEffect)
  useEffect(() => {
    if (!loading) {
      setLastKnownResult(allowed);
    }
  }, [allowed, loading]);

  // If loading and we have a previous result, use it to prevent flickering
  // If loading and no previous result, hide content
  if (loading) {
    if (lastKnownResult !== null) {
      if (typeof children === "function") {
        return <>{children(lastKnownResult)}</>;
      }
      return lastKnownResult ? <>{children}</> : null;
    } else {
      return null;
    }
  }

  // If children is a function, call it with the allowed status
  if (typeof children === "function") {
    return <>{children(allowed)}</>;
  }

  // If allowed, render the children
  if (allowed) {
    return <>{children}</>;
  }

  // If passThrough is true, render the children with disabled styling
  if (passThrough) {
    return (
      <div
        style={{
          opacity: 0.5,
          pointerEvents: "none",
          cursor: "not-allowed",
        }}
      >
        {children}
      </div>
    );
  }

  // Otherwise, render nothing
  return null;
}

// PermissionGuard component moved to its own file
