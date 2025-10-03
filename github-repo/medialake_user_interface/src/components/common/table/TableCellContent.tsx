import React, { memo } from "react";
import { Box, Typography, useTheme, alpha } from "@mui/material";
import { Theme } from "@mui/material/styles";

interface TableCellContentProps {
  children: React.ReactNode;
  variant?: "default" | "primary" | "secondary";
  wordBreak?: "normal" | "break-all" | "break-word" | "keep-all";
  "aria-label"?: string;
}

const getStyles = (
  theme: Theme,
  variant: TableCellContentProps["variant"],
  isDark: boolean,
) => {
  switch (variant) {
    case "primary":
      return {
        color: isDark
          ? alpha(theme.palette.text.primary, 0.95)
          : theme.palette.text.primary,
        fontWeight: 500,
      };
    case "secondary":
      return {
        color: isDark
          ? alpha(theme.palette.text.primary, 0.7)
          : theme.palette.text.secondary,
        opacity: isDark ? 1 : 0.8,
      };
    default:
      return {
        color: isDark
          ? alpha(theme.palette.text.primary, 0.9)
          : theme.palette.text.primary,
      };
  }
};

const TableCellContentBase = ({
  children,
  variant = "default",
  wordBreak = "break-word",
  "aria-label": ariaLabel,
}: TableCellContentProps) => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";
  const styles = getStyles(theme, variant, isDark);

  return (
    <Box
      sx={{
        width: "100%",
        overflow: "visible",
        userSelect: "text",
      }}
      role="cell"
      aria-label={ariaLabel}
    >
      <Typography
        variant="body2"
        sx={{
          ...styles,
          wordBreak,
          whiteSpace: "normal",
          width: "100%",
          userSelect: "text",
          lineHeight: 1.5,
          letterSpacing: "0.01em",
        }}
      >
        {children}
      </Typography>
    </Box>
  );
};

export const TableCellContent = memo(TableCellContentBase);
