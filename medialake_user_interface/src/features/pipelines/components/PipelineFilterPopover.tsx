import React from "react";
import { Popover, Box, TextField, Button, Stack } from "@mui/material";
import { useTranslation } from "react-i18next";

interface PipelineFilterPopoverProps {
  anchorEl: HTMLElement | null;
  column: string | null;
  onClose: () => void;
  onFilterChange: (filters: any[]) => void;
}

export const PipelineFilterPopover: React.FC<PipelineFilterPopoverProps> = ({
  anchorEl,
  column,
  onClose,
  onFilterChange,
}) => {
  const { t } = useTranslation();
  const [filterValue, setFilterValue] = React.useState("");

  const handleApplyFilter = () => {
    if (column) {
      onFilterChange([{ id: column, value: filterValue }]);
      onClose();
    }
  };

  const handleClearFilter = () => {
    setFilterValue("");
    onFilterChange([]);
    onClose();
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
    >
      <Box sx={{ p: 2, width: 300 }}>
        <Stack spacing={2}>
          <TextField
            autoFocus
            fullWidth
            label={t("common.placeholders.filterValue")}
            value={filterValue}
            onChange={(e) => setFilterValue(e.target.value)}
          />
          <Stack direction="row" spacing={1} justifyContent="flex-end">
            <Button onClick={handleClearFilter}>{t("common.clear")}</Button>
            <Button variant="contained" onClick={handleApplyFilter} disabled={!filterValue}>
              {t("common.apply")}
            </Button>
          </Stack>
        </Stack>
      </Box>
    </Popover>
  );
};
