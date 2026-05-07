import React from "react";
import { Box, IconButton, useTheme, alpha } from "@mui/material";
import { ViewColumn as ViewColumnIcon } from "@mui/icons-material";
import { TableDensityToggle } from "../../../../components/common/table/TableDensityToggle";
import { useTranslation } from "react-i18next";
import { SearchField } from "../../../../components/common/SearchField";

interface UserTableToolbarProps {
  globalFilter: string;
  onGlobalFilterChange: (value: string) => void;
  onColumnMenuOpen: (event: React.MouseEvent<HTMLElement>) => void;
  activeFilters?: { columnId: string; value: string }[];
  activeSorting?: { columnId: string; desc: boolean }[];
  onRemoveFilter?: (columnId: string) => void;
  onRemoveSort?: (columnId: string) => void;
}

export const UserTableToolbar: React.FC<UserTableToolbarProps> = ({
  globalFilter,
  onGlobalFilterChange,
  onColumnMenuOpen,
  activeFilters = [],
  activeSorting = [],
  onRemoveFilter,
  onRemoveSort,
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
      <SearchField
        value={globalFilter ?? ""}
        onChange={onGlobalFilterChange}
        placeholder={t("common.search")}
      />
      <Box
        sx={{
          flex: 1,
          display: "flex",
          gap: 1,
          flexWrap: "wrap",
          alignItems: "center",
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
      <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
        <TableDensityToggle />
        <IconButton
          onClick={onColumnMenuOpen}
          sx={{
            height: "40px",
            width: "40px",
            borderRadius: "8px",
            border: `1px solid ${alpha(theme.palette.divider, 0.2)}`,
          }}
        >
          <ViewColumnIcon />
        </IconButton>
      </Box>
    </Box>
  );
};
