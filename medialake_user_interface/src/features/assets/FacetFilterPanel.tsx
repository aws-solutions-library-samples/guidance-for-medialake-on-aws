import React from "react";
import {
  Box,
  Typography,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Checkbox,
  FormControlLabel,
  FormGroup,
  Chip,
  Button,
  Divider,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { useTranslation } from "react-i18next";

export interface FacetValue {
  value: string;
  count: number;
}

export interface Facet {
  field: string;
  label: string;
  values: FacetValue[];
}

export interface SelectedFacets {
  [field: string]: string[];
}

interface FacetFilterPanelProps {
  facets: Facet[];
  selectedFacets: SelectedFacets;
  onFacetChange: (field: string, value: string, checked: boolean) => void;
  onClearAll: () => void;
}

const FacetFilterPanel: React.FC<FacetFilterPanelProps> = ({
  facets,
  selectedFacets,
  onFacetChange,
  onClearAll,
}) => {
  const { t } = useTranslation();

  // Count total selected facets
  const totalSelected = Object.values(selectedFacets).reduce(
    (sum, values) => sum + values.length,
    0
  );

  return (
    <Box
      sx={{
        width: 280,
        borderRight: 1,
        borderColor: "divider",
        height: "100%",
        overflow: "auto",
        p: 2,
      }}
    >
      {/* Header */}
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
        <Typography variant="h6">{t("facetFilter.title") || "Filters"}</Typography>
        {totalSelected > 0 && (
          <Button size="small" onClick={onClearAll}>
            {t("facetFilter.clearAll") || "Clear All"}
          </Button>
        )}
      </Box>

      {/* Selected facets summary */}
      {totalSelected > 0 && (
        <Box sx={{ mb: 2 }}>
          <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: "block" }}>
            {t("facetFilter.activeFilters", { count: totalSelected }) ||
              `${totalSelected} active filter${totalSelected > 1 ? "s" : ""}`}
          </Typography>
          <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}>
            {Object.entries(selectedFacets).map(([field, values]) =>
              values.map((value) => (
                <Chip
                  key={`${field}-${value}`}
                  label={value}
                  size="small"
                  onDelete={() => onFacetChange(field, value, false)}
                />
              ))
            )}
          </Box>
        </Box>
      )}

      <Divider sx={{ mb: 2 }} />

      {/* Facet accordions */}
      {facets.map((facet) => (
        <Accordion key={facet.field} defaultExpanded disableGutters elevation={0}>
          <AccordionSummary
            expandIcon={<ExpandMoreIcon />}
            sx={{
              minHeight: 48,
              "&.Mui-expanded": {
                minHeight: 48,
              },
            }}
          >
            <Typography variant="subtitle2">{facet.label}</Typography>
            {selectedFacets[facet.field]?.length > 0 && (
              <Chip
                label={selectedFacets[facet.field].length}
                size="small"
                sx={{ ml: 1, height: 20, fontSize: "0.75rem" }}
              />
            )}
          </AccordionSummary>
          <AccordionDetails sx={{ pt: 0 }}>
            <FormGroup>
              {facet.values.map((facetValue) => (
                <FormControlLabel
                  key={facetValue.value}
                  control={
                    <Checkbox
                      checked={selectedFacets[facet.field]?.includes(facetValue.value) || false}
                      onChange={(e) =>
                        onFacetChange(facet.field, facetValue.value, e.target.checked)
                      }
                      size="small"
                    />
                  }
                  label={
                    <Box sx={{ display: "flex", justifyContent: "space-between", width: "100%" }}>
                      <Typography variant="body2">{facetValue.value}</Typography>
                      <Typography variant="caption" color="text.secondary">
                        {facetValue.count}
                      </Typography>
                    </Box>
                  }
                  sx={{ width: "100%" }}
                />
              ))}
            </FormGroup>
          </AccordionDetails>
        </Accordion>
      ))}

      {/* Empty state */}
      {facets.length === 0 && (
        <Typography variant="body2" color="text.secondary" sx={{ textAlign: "center", mt: 4 }}>
          {t("facetFilter.noFiltersAvailable") || "No filters available"}
        </Typography>
      )}
    </Box>
  );
};

export default FacetFilterPanel;
