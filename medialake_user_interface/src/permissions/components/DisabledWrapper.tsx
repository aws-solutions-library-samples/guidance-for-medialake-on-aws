import React from "react";
import { Tooltip, Box } from "@mui/material";
import { useTranslation } from "react-i18next";

interface DisabledWrapperProps {
  /** Whether the wrapped content should be disabled */
  disabled: boolean;
  /** Optional custom tooltip text. Falls back to a default "no permission" message */
  tooltip?: string;
  /** The content to wrap */
  children: React.ReactNode;
  /** If true, renders children completely hidden instead of greyed out */
  hidden?: boolean;
}

/**
 * Wraps children with a greyed-out, non-interactive overlay when disabled.
 * Shows a tooltip explaining why the element is disabled.
 */
export function DisabledWrapper({
  disabled,
  tooltip,
  children,
  hidden = false,
}: DisabledWrapperProps) {
  const { t } = useTranslation();

  if (hidden && disabled) {
    return null;
  }

  if (!disabled) {
    return <>{children}</>;
  }

  const tooltipText =
    tooltip || t("permissions.noPermission", "You don't have permission to perform this action");

  return (
    <Tooltip title={tooltipText} arrow placement="right">
      <Box
        sx={{
          opacity: 0.45,
          pointerEvents: "none",
          cursor: "not-allowed",
          userSelect: "none",
          "& *": {
            pointerEvents: "none !important",
          },
        }}
        aria-disabled="true"
      >
        {children}
      </Box>
    </Tooltip>
  );
}
