import React from "react";
import { Button as MuiButton, ButtonProps as MuiButtonProps } from "@mui/material";

export interface ButtonProps extends Omit<MuiButtonProps, "size"> {
  startIcon?: React.ReactNode;
  endIcon?: React.ReactNode;
  fullWidth?: boolean;
}

/**
 * Thin wrapper around MuiButton.
 * All visual styling (border-radius, font-weight, colors) is handled by the
 * MuiButton theme overrides in theme.ts — this component only adds a
 * consistent height so callers don't have to repeat it.
 */
export const Button: React.FC<ButtonProps> = ({ children, sx, ...props }) => {
  return (
    <MuiButton
      sx={{
        height: "40px",
        minWidth: "80px",
        ...sx,
      }}
      {...props}
    >
      {children}
    </MuiButton>
  );
};

export default Button;
