import React from "react";
import { Button, ButtonProps, CircularProgress } from "@mui/material";

interface ActionButtonProps extends ButtonProps {
  loading?: boolean;
}

export const ActionButton: React.FC<ActionButtonProps> = ({
  children,
  loading = false,
  disabled,
  startIcon,
  ...props
}) => {
  return (
    <Button
      {...props}
      disabled={loading || disabled}
      startIcon={loading ? <CircularProgress size={20} /> : startIcon}
    >
      {children}
    </Button>
  );
};
