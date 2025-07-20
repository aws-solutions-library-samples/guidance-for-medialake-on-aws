// components/TopBar/FilterPopover/FilterSection.tsx
import React from "react";
import {
  Box,
  Typography,
  Grid,
  FormControlLabel,
  Checkbox,
} from "@mui/material";
import { FilterSectionType } from "../../TopBar/types";

interface FilterSectionProps {
  title: string;
  section: FilterSectionType;
  onCheckboxChange: (
    option: string,
  ) => (event: React.ChangeEvent<HTMLInputElement>) => void;
}

const FilterSection: React.FC<FilterSectionProps> = ({
  title,
  section,
  onCheckboxChange,
}) => (
  <Box sx={{ mb: 1 }}>
    <Typography variant="subtitle2" gutterBottom>
      {title}
    </Typography>
    <Grid container>
      {(Object.entries(section.types) as [string, boolean][]).map(
        ([option, checked]) => (
          <FormControlLabel
            key={option}
            control={
              <Checkbox
                checked={checked}
                onChange={onCheckboxChange(option)}
                name={option}
                size="small"
              />
            }
            label={option.toUpperCase()}
          />
        ),
      )}
    </Grid>
  </Box>
);

export default React.memo(FilterSection);
