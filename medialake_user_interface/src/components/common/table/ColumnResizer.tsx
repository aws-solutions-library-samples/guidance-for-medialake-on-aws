// ColumnResizer.tsx
import React from "react";
import { Box, useTheme, SxProps, Theme, alpha } from "@mui/material";
import { Header } from "@tanstack/react-table";

interface ColumnResizerProps {
  header: Header<any, unknown>;
  className?: string;
  sx?: SxProps<Theme>;
}

export const ColumnResizer: React.FC<ColumnResizerProps> = ({
  header,
  className,
  sx = {},
}) => {
  const theme = useTheme();

  return (
    <Box
      className={className}
      onMouseDown={header.getResizeHandler()}
      onTouchStart={header.getResizeHandler()}
      sx={{
        position: "absolute",
        right: -2,
        top: 0,
        height: "100%",
        width: 4,
        cursor: "col-resize",
        userSelect: "none",
        touchAction: "none",
        "&::after": {
          content: '""',
          position: "absolute",
          right: 1,
          top: 0,
          width: 2,
          height: "100%",
          backgroundColor: header.column.getIsResizing()
            ? theme.palette.primary.main
            : alpha(theme.palette.divider, 0.2),
          transition: "background-color 0.2s ease",
        },
        "&:hover::after": {
          backgroundColor: theme.palette.primary.main,
        },
        zIndex: 1,
        ...sx,
      }}
    />
  );
};
