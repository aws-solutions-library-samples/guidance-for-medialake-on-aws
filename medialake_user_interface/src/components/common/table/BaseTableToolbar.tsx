import React from "react";
import { Box, IconButton, useTheme, alpha } from "@mui/material";
import { ViewColumn as ViewColumnIcon } from "@mui/icons-material";
import { TableDensityToggle } from "./TableDensityToggle";
import { useTranslation } from "react-i18next";
import { SearchField } from "../SearchField";

export interface BaseTableToolbarProps {
  globalFilter: string;
  onGlobalFilterChange: (value: string) => void;
  onColumnMenuOpen: (event: React.MouseEvent<HTMLElement>) => void;
  activeFilters?: { columnId: string; value: string }[];
  activeSorting?: { columnId: string; desc: boolean }[];
  onRemoveFilter?: (columnId: string) => void;
  onRemoveSort?: (columnId: string) => void;
  searchPlaceholder?: string;
}

export const BaseTableToolbar: React.FC<BaseTableToolbarProps> = ({
  globalFilter,
  onGlobalFilterChange,
  onColumnMenuOpen,
  activeFilters = [],
  activeSorting = [],
  onRemoveFilter,
  onRemoveSort,
  searchPlaceholder,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();

  return (
    <Box
      sx={{
        display: "flex",
        gap: 2,
        mb: 3,
        alignItems: "center",
        height: "40px",
        width: "100%",
      }}
    >
      <Box
        sx={{
          display: "flex",
          gap: 2,
          alignItems: "center",
          flex: 1,
          overflow: "hidden",
        }}
      >
        <SearchField
          value={globalFilter ?? ""}
          onChange={onGlobalFilterChange}
          placeholder={searchPlaceholder || t("common.search")}
        />
        <Box
          sx={{
            display: "flex",
            gap: 1,
            flexWrap: "wrap",
            alignItems: "center",
            overflow: "hidden",
          }}
        >
          {activeFilters.map(({ columnId, value }) => (
            <Box
              key={`filter-${columnId}`}
              sx={{
                display: "inline-flex",
                alignItems: "center",
                px: 2,
                py: 0.5,
                borderRadius: "16px",
                backgroundColor: alpha(theme.palette.primary.main, 0.1),
                color: theme.palette.primary.main,
              }}
            >
              <Box component="span" sx={{ mr: 1 }}>
                {`${columnId}: ${value}`}
              </Box>
              {onRemoveFilter && (
                <Box
                  component="span"
                  onClick={() => onRemoveFilter(columnId)}
                  sx={{
                    cursor: "pointer",
                    fontSize: "1.2rem",
                    lineHeight: 1,
                    "&:hover": { opacity: 0.7 },
                  }}
                >
                  ×
                </Box>
              )}
            </Box>
          ))}
          {activeSorting.map(({ columnId, desc }) => (
            <Box
              key={`sort-${columnId}`}
              sx={{
                display: "inline-flex",
                alignItems: "center",
                px: 2,
                py: 0.5,
                borderRadius: "16px",
                backgroundColor: alpha(theme.palette.secondary.main, 0.1),
                color: theme.palette.secondary.main,
              }}
            >
              <Box component="span" sx={{ mr: 1 }}>
                {`Sorted by: ${columnId} (${desc ? "desc" : "asc"})`}
              </Box>
              {onRemoveSort && (
                <Box
                  component="span"
                  onClick={() => onRemoveSort(columnId)}
                  sx={{
                    cursor: "pointer",
                    fontSize: "1.2rem",
                    lineHeight: 1,
                    "&:hover": { opacity: 0.7 },
                  }}
                >
                  ×
                </Box>
              )}
            </Box>
          ))}
        </Box>
      </Box>
      <Box
        sx={{ display: "flex", gap: 1, alignItems: "center", flexShrink: 0 }}
      >
        <TableDensityToggle />
        <IconButton
          onClick={onColumnMenuOpen}
          size="small"
          sx={{
            height: "32px",
            width: "32px",
            borderRadius: "6px",
            border: `1px solid ${alpha(theme.palette.divider, 0.2)}`,
            "& .MuiSvgIcon-root": {
              fontSize: "1.2rem",
            },
          }}
        >
          <ViewColumnIcon fontSize="small" />
        </IconButton>
      </Box>
    </Box>
  );
};
