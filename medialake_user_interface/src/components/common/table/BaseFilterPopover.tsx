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
  IconButton,
} from "@mui/material";
import { Close as CloseIcon } from "@mui/icons-material";
import { Column } from "@tanstack/react-table";
import { useTranslation } from "react-i18next";

export interface BaseFilterPopoverProps<T> {
  anchorEl: HTMLElement | null;
  column: Column<T, unknown> | null;
  onClose: () => void;
  data: T[];
  getUniqueValues: (columnId: string, data: T[]) => string[];
  formatValue?: (columnId: string, value: string) => string;
}

export function BaseFilterPopover<T>({
  anchorEl,
  column,
  onClose,
  data,
  getUniqueValues,
  formatValue,
}: BaseFilterPopoverProps<T>) {
  const { t } = useTranslation();
  const theme = useTheme();

  if (!column) return null;

  const uniqueValues = getUniqueValues(column.id, data);
  const currentValue = column.getFilterValue() as string;

  const handleTextFilterChange = (value: string) => {
    if (value) {
      column.setFilterValue(value);
    } else {
      column.setFilterValue("");
    }
  };

  const handleTextFilterSubmit = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      e.stopPropagation();
      onClose();
    }
  };

  const handleSelectFilterChange = (value: string) => {
    if (value) {
      column.setFilterValue(value);
    } else {
      column.setFilterValue("");
    }
    onClose();
  };

  const handleClearFilter = () => {
    column.setFilterValue("");
  };

  const displayValue = (value: string) => {
    if (formatValue) {
      return formatValue(column.id, value);
    }
    return value;
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
          position: "relative",
        },
      }}
    >
      <IconButton
        onClick={onClose}
        size="small"
        sx={{
          position: "absolute",
          right: 8,
          top: 8,
          color: theme.palette.text.secondary,
          "&:hover": {
            color: theme.palette.text.primary,
          },
        }}
      >
        <CloseIcon fontSize="small" />
      </IconButton>
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
                {displayValue(value)}
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
}
