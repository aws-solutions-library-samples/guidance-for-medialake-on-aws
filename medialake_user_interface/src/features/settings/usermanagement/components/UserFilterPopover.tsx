import React from "react";
import {
  Box,
  TextField,
  Popover,
  Select,
  MenuItem,
  Button,
  useTheme,
  Typography,
  Stack,
} from "@mui/material";
import { Column } from "@tanstack/react-table";
import { User } from "@/api/types/api.types";
import { useTranslation } from "react-i18next";

interface UserFilterPopoverProps {
  anchorEl: HTMLElement | null;
  column: Column<User, unknown> | null;
  onClose: () => void;
  users: User[];
}

export const UserFilterPopover: React.FC<UserFilterPopoverProps> = ({
  anchorEl,
  column,
  onClose,
  users,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();

  const formatDateOnly = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString();
  };

  const getUniqueColumnValues = (columnId: string) => {
    const values = new Set<string>();
    users.forEach((user) => {
      const value = user[columnId as keyof User];
      if (value != null) {
        if (Array.isArray(value)) {
          if (columnId === "roles") {
            // For roles, only add the first role (primary role)
            if (value.length > 0) {
              values.add(String(value[0]));
            } else {
              values.add("No Role");
            }
          } else {
            // Handle other arrays (like groups)
            value.forEach((v) => values.add(String(v)));
          }
        } else if (typeof value === "boolean") {
          // Handle boolean values (like enabled)
          values.add(value ? "true" : "false");
        } else if (columnId === "created" || columnId === "modified") {
          // Handle date columns
          values.add(formatDateOnly(String(value)));
        } else {
          // Handle other values
          values.add(String(value));
        }
      }
    });
    return Array.from(values).sort();
  };

  if (!column) return null;

  const uniqueValues = getUniqueColumnValues(column.id);
  const currentValue = column.getFilterValue() as string;

  const handleTextFilterChange = (value: string) => {
    if (value) {
      // Clear select filter when typing
      column.setFilterValue(value);
    } else {
      column.setFilterValue("");
    }
  };

  const handleSelectFilterChange = (value: string) => {
    if (column) {
      column.setFilterValue(value);
      onClose(); // Close popover after selection
    }
  };

  const handleTextFilterSubmit = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      onClose(); // Close popover on Enter
    }
  };

  const handleClearFilter = () => {
    column.setFilterValue("");
  };

  return (
    <Popover
      open={Boolean(anchorEl)}
      anchorEl={anchorEl}
      onClose={onClose}
      anchorOrigin={{
        vertical: "bottom",
        horizontal: "left",
      }}
      transformOrigin={{
        vertical: "top",
        horizontal: "left",
      }}
      PaperProps={{
        sx: {
          p: 2,
          width: 300,
          borderRadius: "8px",
        },
      }}
    >
      <Stack spacing={2}>
        <Box>
          <Typography
            variant="caption"
            color="textSecondary"
            sx={{ mb: 1, display: "block" }}
          >
            {t("common.textFilter")}
          </Typography>
          <TextField
            fullWidth
            size="small"
            placeholder={`${t("common.filter")} ${column.columnDef.header as string}`}
            value={currentValue ?? ""}
            onChange={(e) => handleTextFilterChange(e.target.value)}
            onKeyDown={handleTextFilterSubmit}
            sx={{
              "& .MuiOutlinedInput-root": {
                borderRadius: "8px",
              },
            }}
          />
        </Box>

        <Box>
          <Typography
            variant="caption"
            color="textSecondary"
            sx={{ mb: 1, display: "block" }}
          >
            {t("common.selectFilter")}
          </Typography>
          <Select
            fullWidth
            size="small"
            value={currentValue ?? ""}
            onChange={(e) => handleSelectFilterChange(e.target.value)}
            displayEmpty
            sx={{
              borderRadius: "8px",
            }}
          >
            <MenuItem value="">
              <em>{t("common.all")}</em>
            </MenuItem>
            {uniqueValues.map((value) => (
              <MenuItem key={value} value={value}>
                {column.id === "enabled"
                  ? value === "true"
                    ? t("users.status.active")
                    : t("users.status.inactive")
                  : value}
              </MenuItem>
            ))}
          </Select>
        </Box>

        {currentValue && (
          <Button
            size="small"
            onClick={handleClearFilter}
            sx={{ alignSelf: "flex-start" }}
          >
            {t("common.clearFilter")}
          </Button>
        )}
      </Stack>
    </Popover>
  );
};
