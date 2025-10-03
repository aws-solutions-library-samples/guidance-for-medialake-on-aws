import React from "react";
import {
  Menu,
  MenuItem,
  Typography,
  FormControlLabel,
  Checkbox,
  useTheme,
} from "@mui/material";
import { Column } from "@tanstack/react-table";

interface ColumnVisibilityMenuProps {
  anchorEl: HTMLElement | null;
  columns: Column<any, unknown>[];
  onClose: () => void;
  excludeIds?: string[];
}

export const ColumnVisibilityMenu: React.FC<ColumnVisibilityMenuProps> = ({
  anchorEl,
  columns,
  onClose,
  excludeIds = ["actions"],
}) => {
  const theme = useTheme();

  return (
    <Menu
      anchorEl={anchorEl}
      open={Boolean(anchorEl)}
      onClose={onClose}
      PaperProps={{
        elevation: 3,
        sx: {
          maxHeight: 300,
          width: 180,
          borderRadius: "8px",
          "& .MuiList-root": {
            p: 0.5,
          },
        },
      }}
    >
      {columns.map((column) => {
        if (excludeIds.includes(column.id)) return null;
        return (
          <MenuItem
            key={column.id}
            dense
            sx={{
              py: 0.25,
              px: 1,
              minHeight: 32,
              borderRadius: "4px",
            }}
          >
            <FormControlLabel
              control={
                <Checkbox
                  checked={column.getIsVisible()}
                  onChange={column.getToggleVisibilityHandler()}
                  size="small"
                  sx={{
                    p: 0.5,
                    mr: 1,
                    "& .MuiSvgIcon-root": {
                      fontSize: "1.2rem",
                    },
                  }}
                />
              }
              label={
                <Typography
                  variant="body2"
                  sx={{
                    fontSize: "0.875rem",
                    lineHeight: 1.2,
                  }}
                >
                  {column.columnDef.header as string}
                </Typography>
              }
              sx={{
                m: 0,
                "& .MuiFormControlLabel-label": {
                  userSelect: "none",
                },
              }}
            />
          </MenuItem>
        );
      })}
    </Menu>
  );
};
