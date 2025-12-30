// components/TopBar/FilterPopover/DateFilter.tsx
import React from "react";
import { Grid, FormControlLabel, Switch } from "@mui/material";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDateFns } from "@mui/x-date-pickers/AdapterDateFns";
import { useTranslation } from "react-i18next";

interface DateFilterProps {
  enabled: boolean;
  before: Date | null;
  after: Date | null;
  onToggle: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onDateChange: (type: "before" | "after") => (date: Date | null) => void;
}

const DateFilter: React.FC<DateFilterProps> = ({
  enabled,
  before,
  after,
  onToggle,
  onDateChange,
}) => {
  const { t } = useTranslation();

  return (
    <div>
      <FormControlLabel
        control={<Switch checked={enabled} onChange={onToggle} name="creation-date-toggle" />}
        label={t("search.filters.creationDate")}
      />
      {enabled && (
        <Grid container spacing={2} sx={{ mt: 1 }}>
          <Grid item xs={12} sm={6}>
            <LocalizationProvider dateAdapter={AdapterDateFns}>
              <DatePicker
                label={t("search.filters.after")}
                value={after}
                onChange={onDateChange("after")}
              />
            </LocalizationProvider>
          </Grid>
          <Grid item xs={12} sm={6}>
            <LocalizationProvider dateAdapter={AdapterDateFns}>
              <DatePicker
                label={t("search.filters.before")}
                value={before}
                onChange={onDateChange("before")}
              />
            </LocalizationProvider>
          </Grid>
        </Grid>
      )}
    </div>
  );
};

export default React.memo(DateFilter);
