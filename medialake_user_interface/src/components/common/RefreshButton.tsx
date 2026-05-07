import React from "react";
import { IconButton, Button, Tooltip, useTheme } from "@mui/material";
import { Refresh as RefreshIcon } from "@mui/icons-material";
import { alpha } from "@mui/material/styles";
import { useTranslation } from "react-i18next";

interface RefreshButtonProps {
  onRefresh: () => void | Promise<void>;
  isRefreshing?: boolean;
  disabled?: boolean;
  variant?: "icon" | "button";
  label?: string;
  size?: "small" | "medium" | "large";
  tooltip?: string;
}

const RefreshButton: React.FC<RefreshButtonProps> = ({
  onRefresh,
  isRefreshing = false,
  disabled = false,
  variant = "icon",
  label,
  size = "medium",
  tooltip,
}) => {
  const theme = useTheme();
  const { t } = useTranslation();

  const defaultLabel = label || t("common.refresh", "Refresh");
  const defaultTooltip = tooltip || defaultLabel;

  const iconStyles = {
    animation: isRefreshing ? "spin 1s linear infinite" : "none",
    "@keyframes spin": {
      "0%": {
        transform: "rotate(0deg)",
      },
      "100%": {
        transform: "rotate(360deg)",
      },
    },
  };

  const buttonStyles = {
    backgroundColor: alpha(theme.palette.primary.main, 0.1),
    color: theme.palette.primary.main,
    "&:hover": {
      backgroundColor: alpha(theme.palette.primary.main, 0.2),
    },
    "&:disabled": {
      backgroundColor: alpha(theme.palette.action.disabled, 0.1),
    },
  };

  if (variant === "button") {
    return (
      <Button
        onClick={onRefresh}
        disabled={disabled || isRefreshing}
        size={size}
        sx={buttonStyles}
        startIcon={<RefreshIcon sx={iconStyles} />}
        aria-label={defaultLabel}
      >
        {defaultLabel}
      </Button>
    );
  }

  return (
    <Tooltip title={defaultTooltip}>
      <span>
        <IconButton
          onClick={onRefresh}
          disabled={disabled || isRefreshing}
          size={size}
          sx={buttonStyles}
          aria-label={defaultLabel}
        >
          <RefreshIcon sx={iconStyles} />
        </IconButton>
      </span>
    </Tooltip>
  );
};

export default RefreshButton;
