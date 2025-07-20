import React, { useState, useRef } from "react";
import { FacetFilters } from "../../types/facetSearch";
import {
  Box,
  Popover,
  Typography,
  Divider,
  Tabs,
  Tab,
  FormGroup,
  FormControlLabel,
  Checkbox,
  TextField,
  MenuItem,
  Select,
  FormControl,
  Button,
  Chip,
  Stack,
  IconButton,
  useTheme,
  Paper,
  Grid,
} from "@mui/material";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDateFns } from "@mui/x-date-pickers/AdapterDateFns";
import {
  FilterList as FilterListIcon,
  ImageOutlined as ImageIcon,
  InsertDriveFileOutlined as FileIcon,
  AspectRatioOutlined as SizeIcon,
  DateRangeOutlined as DateIcon,
  TextFieldsOutlined as TextIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";

// File size units for conversion
const FILE_SIZE_UNITS = [
  { value: 1, label: "B" },
  { value: 1024, label: "KB" },
  { value: 1024 * 1024, label: "MB" },
  { value: 1024 * 1024 * 1024, label: "GB" },
];

export interface FacetSearchProps {
  onApplyFilters: (filters: FacetFilters) => void;
  facetCounts?: {
    asset_types?: { buckets: Array<{ key: string; doc_count: number }> };
    file_extensions?: { buckets: Array<{ key: string; doc_count: number }> };
    file_size_ranges?: { buckets: Array<{ key: string; doc_count: number }> };
    ingestion_date?: { buckets: Array<{ key: string; doc_count: number }> };
  };
  activeFilters?: FacetFilters;
  searchBoxWidth?: number;
}

const FacetSearch: React.FC<FacetSearchProps> = ({
  onApplyFilters,
  facetCounts,
  activeFilters = {},
  searchBoxWidth,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const [anchorEl, setAnchorEl] = useState<HTMLButtonElement | null>(null);
  const [filters, setFilters] = useState<FacetFilters>(activeFilters);
  const [currentTab, setCurrentTab] = useState(0);

  // State for file size inputs
  const [minSizeValue, setMinSizeValue] = useState<number | "">("");
  const [minSizeUnit, setMinSizeUnit] = useState<number>(1024 * 1024); // Default to MB
  const [maxSizeValue, setMaxSizeValue] = useState<number | "">("");
  const [maxSizeUnit, setMaxSizeUnit] = useState<number>(1024 * 1024); // Default to MB

  // State for date pickers
  const [startDate, setStartDate] = useState<Date | null>(
    filters.ingested_date_gte ? new Date(filters.ingested_date_gte) : null,
  );
  const [endDate, setEndDate] = useState<Date | null>(
    filters.ingested_date_lte ? new Date(filters.ingested_date_lte) : null,
  );

  // Count active filters
  const activeFilterCount = Object.values(activeFilters).filter(Boolean).length;

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  // Helper function to apply filters with conversions
  const applyFiltersWithConversions = (newFilters = filters) => {
    const updatedFilters = { ...newFilters };

    // Convert size inputs to bytes for API
    if (minSizeValue !== "") {
      updatedFilters.asset_size_gte = Number(minSizeValue) * minSizeUnit;
    }

    if (maxSizeValue !== "") {
      updatedFilters.asset_size_lte = Number(maxSizeValue) * maxSizeUnit;
    }

    // Convert dates to ISO strings
    if (startDate) {
      updatedFilters.ingested_date_gte = startDate.toISOString().split("T")[0];
    }

    if (endDate) {
      updatedFilters.ingested_date_lte = endDate.toISOString().split("T")[0];
    }

    onApplyFilters(updatedFilters);
  };

  const handleApply = () => {
    applyFiltersWithConversions();
    handleClose();
  };

  const handleClearFilters = () => {
    setFilters({});
    setMinSizeValue("");
    setMaxSizeValue("");
    setStartDate(null);
    setEndDate(null);
    onApplyFilters({});
    // Don't close the popover automatically on clear
    // This allows users to see that filters were cleared and select new ones
  };

  const handleTypeChange = (type: string) => {
    const newFilters = {
      ...filters,
      type: filters.type === type ? undefined : type,
    };
    setFilters(newFilters);

    // Auto-apply the filter
    onApplyFilters(newFilters);
  };

  const handleExtensionChange = (extension: string) => {
    const newFilters = {
      ...filters,
      extension: filters.extension === extension ? undefined : extension,
    };
    setFilters(newFilters);

    // Auto-apply the filter
    onApplyFilters(newFilters);
  };

  const handleFilenameChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    // For text input, don't auto-apply on every keystroke
    setFilters((prev) => ({
      ...prev,
      filename: event.target.value || undefined,
    }));
  };

  const open = Boolean(anchorEl);
  const id = open ? "facet-search-popover" : undefined;

  // Group extensions by type for better organization
  const extensionsByType: Record<string, string[]> = {
    Image: ["jpg", "jpeg", "png", "gif", "svg", "webp", "tiff"],
    Video: ["mp4", "mov", "avi", "wmv", "flv", "webm", "mkv"],
    Audio: ["mp3", "wav", "ogg", "flac", "aac", "m4a"],
    Document: ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt"],
  };

  // Get available types from facet counts if available
  const availableTypes = facetCounts?.asset_types?.buckets || [
    { key: "Image", doc_count: 0 },
    { key: "Video", doc_count: 0 },
    { key: "Audio", doc_count: 0 },
    { key: "Document", doc_count: 0 },
  ];

  // Get available extensions from facet counts if available
  const availableExtensions = facetCounts?.file_extensions?.buckets || [];

  // Create a ref for the root element to use as the anchor for the popover
  const rootRef = useRef<HTMLDivElement>(null);

  return (
    <Box ref={rootRef} sx={{ position: "relative" }}>
      <IconButton
        aria-describedby={id}
        onClick={handleClick}
        size="small"
        sx={{
          position: "relative",
          color: theme.palette.text.secondary,
        }}
      >
        <FilterListIcon />
        {activeFilterCount > 0 && (
          <Box
            sx={{
              position: "absolute",
              top: -2,
              right: -2,
              backgroundColor: theme.palette.primary.main,
              color: theme.palette.primary.contrastText,
              borderRadius: "50%",
              width: 16,
              height: 16,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "0.75rem",
              fontWeight: "bold",
            }}
          >
            {activeFilterCount}
          </Box>
        )}
      </IconButton>

      <Popover
        id={id}
        open={open}
        // Use the parent search box ref instead of the button
        anchorEl={rootRef.current?.parentElement?.parentElement || anchorEl}
        onClose={handleClose}
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
            width: searchBoxWidth || 600,
            maxHeight: 400,
            overflow: "hidden",
            mt: 1,
          },
        }}
      >
        <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
          {/* Header with title and clear button */}
          <Box
            sx={{
              px: 2,
              py: 1,
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              borderBottom: 1,
              borderColor: "divider",
            }}
          >
            <Typography variant="subtitle1">
              {t("search.filters.title", "Filters")}
            </Typography>
            <Button
              size="small"
              onClick={handleClearFilters}
              disabled={!activeFilterCount}
            >
              {t("search.filters.clearAll", "Clear All")}
            </Button>
          </Box>

          {/* Horizontal tabs */}
          <Tabs
            value={currentTab}
            onChange={(_, newValue) => setCurrentTab(newValue)}
            variant="fullWidth"
            sx={{
              borderBottom: 1,
              borderColor: "divider",
              minHeight: 48,
              "& .MuiTab-root": {
                minHeight: 48,
                py: 0.5,
              },
            }}
          >
            <Tab
              icon={<ImageIcon fontSize="small" />}
              label="Media Type"
              iconPosition="start"
            />
            <Tab
              icon={<FileIcon fontSize="small" />}
              label="Extension"
              iconPosition="start"
            />
            <Tab
              icon={<SizeIcon fontSize="small" />}
              label="Size"
              iconPosition="start"
            />
            <Tab
              icon={<DateIcon fontSize="small" />}
              label="Date"
              iconPosition="start"
            />
            <Tab
              icon={<TextIcon fontSize="small" />}
              label="Filename"
              iconPosition="start"
            />
          </Tabs>

          {/* Tab content area */}
          <Box sx={{ p: 2, overflow: "auto", flexGrow: 1 }}>
            {/* Media Type Tab */}
            {currentTab === 0 && (
              <Grid container spacing={1}>
                {availableTypes.map((type) => (
                  <Grid item xs={6} key={type.key}>
                    <FormControlLabel
                      control={
                        <Checkbox
                          checked={filters.type === type.key}
                          onChange={() => handleTypeChange(type.key)}
                          size="small"
                        />
                      }
                      label={
                        <Typography variant="body2">
                          {type.key}{" "}
                          {type.doc_count > 0 && `(${type.doc_count})`}
                        </Typography>
                      }
                    />
                  </Grid>
                ))}
              </Grid>
            )}

            {/* File Extension Tab */}
            {currentTab === 1 && (
              <Box>
                {availableExtensions.length > 0 ? (
                  <Grid container spacing={1}>
                    {availableExtensions.map((ext) => (
                      <Grid item xs={4} key={ext.key}>
                        <FormControlLabel
                          control={
                            <Checkbox
                              checked={filters.extension === ext.key}
                              onChange={() => handleExtensionChange(ext.key)}
                              size="small"
                            />
                          }
                          label={
                            <Typography variant="body2" noWrap>
                              {ext.key} ({ext.doc_count})
                            </Typography>
                          }
                        />
                      </Grid>
                    ))}
                  </Grid>
                ) : (
                  <Box>
                    {Object.entries(extensionsByType).map(
                      ([type, extensions]) => (
                        <Box key={type} sx={{ mb: 1.5 }}>
                          <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                            {type}
                          </Typography>
                          <Stack
                            direction="row"
                            spacing={0.5}
                            flexWrap="wrap"
                            useFlexGap
                          >
                            {extensions.map((ext) => (
                              <Chip
                                key={ext}
                                label={ext}
                                size="small"
                                onClick={() => handleExtensionChange(ext)}
                                color={
                                  filters.extension === ext
                                    ? "primary"
                                    : "default"
                                }
                                sx={{ mb: 0.5, mr: 0.5 }}
                              />
                            ))}
                          </Stack>
                        </Box>
                      ),
                    )}
                  </Box>
                )}
              </Box>
            )}

            {/* File Size Tab */}
            {currentTab === 2 && (
              <Grid container spacing={2}>
                <Grid item xs={6}>
                  <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                    {t("search.filters.minSize", "Minimum Size")}
                  </Typography>
                  <Box sx={{ display: "flex", gap: 1 }}>
                    <TextField
                      type="number"
                      size="small"
                      value={minSizeValue}
                      onChange={(e) => {
                        const newValue =
                          e.target.value === "" ? "" : Number(e.target.value);
                        setMinSizeValue(newValue);
                        // Don't auto-apply on every keystroke for number inputs
                      }}
                      onBlur={() => applyFiltersWithConversions()} // Apply on blur
                      inputProps={{ min: 0 }}
                      sx={{ flex: 1 }}
                    />
                    <FormControl size="small" sx={{ width: 70 }}>
                      <Select
                        value={minSizeUnit}
                        onChange={(e) => {
                          setMinSizeUnit(Number(e.target.value));
                          applyFiltersWithConversions(); // Apply when unit changes
                        }}
                      >
                        {FILE_SIZE_UNITS.map((unit) => (
                          <MenuItem key={unit.value} value={unit.value}>
                            {unit.label}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </Box>
                </Grid>

                <Grid item xs={6}>
                  <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                    {t("search.filters.maxSize", "Maximum Size")}
                  </Typography>
                  <Box sx={{ display: "flex", gap: 1 }}>
                    <TextField
                      type="number"
                      size="small"
                      value={maxSizeValue}
                      onChange={(e) => {
                        const newValue =
                          e.target.value === "" ? "" : Number(e.target.value);
                        setMaxSizeValue(newValue);
                        // Don't auto-apply on every keystroke for number inputs
                      }}
                      onBlur={() => applyFiltersWithConversions()} // Apply on blur
                      inputProps={{ min: 0 }}
                      sx={{ flex: 1 }}
                    />
                    <FormControl size="small" sx={{ width: 70 }}>
                      <Select
                        value={maxSizeUnit}
                        onChange={(e) => {
                          setMaxSizeUnit(Number(e.target.value));
                          applyFiltersWithConversions(); // Apply when unit changes
                        }}
                      >
                        {FILE_SIZE_UNITS.map((unit) => (
                          <MenuItem key={unit.value} value={unit.value}>
                            {unit.label}
                          </MenuItem>
                        ))}
                      </Select>
                    </FormControl>
                  </Box>
                </Grid>
              </Grid>
            )}

            {/* Date Range Tab */}
            {currentTab === 3 && (
              <LocalizationProvider dateAdapter={AdapterDateFns}>
                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                      {t("search.filters.fromDate", "From Date")}
                    </Typography>
                    <DatePicker
                      value={startDate}
                      onChange={(newValue) => {
                        setStartDate(newValue);
                        // Apply after a short delay to ensure state is updated
                        setTimeout(() => applyFiltersWithConversions(), 0);
                      }}
                      slotProps={{
                        textField: { size: "small", fullWidth: true },
                      }}
                    />
                  </Grid>

                  <Grid item xs={6}>
                    <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                      {t("search.filters.toDate", "To Date")}
                    </Typography>
                    <DatePicker
                      value={endDate}
                      onChange={(newValue) => {
                        setEndDate(newValue);
                        // Apply after a short delay to ensure state is updated
                        setTimeout(() => applyFiltersWithConversions(), 0);
                      }}
                      slotProps={{
                        textField: { size: "small", fullWidth: true },
                      }}
                    />
                  </Grid>
                </Grid>
              </LocalizationProvider>
            )}

            {/* Filename Tab */}
            {currentTab === 4 && (
              <Box>
                <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                  {t("search.filters.filenameSearch", "Search by filename")}
                </Typography>
                <TextField
                  fullWidth
                  size="small"
                  placeholder={t(
                    "search.filters.filenameSearch",
                    "Search by filename",
                  )}
                  value={filters.filename || ""}
                  onChange={handleFilenameChange}
                  onBlur={() => applyFiltersWithConversions()} // Apply on blur
                />
              </Box>
            )}
          </Box>

          {/* Footer with apply button */}
          <Box
            sx={{
              p: 1.5,
              display: "flex",
              justifyContent: "flex-end",
              borderTop: 1,
              borderColor: "divider",
            }}
          >
            <Button variant="contained" onClick={handleApply} size="small">
              {t("search.filters.apply", "Apply Filters")}
            </Button>
          </Box>
        </Box>
      </Popover>
    </Box>
  );
};

export default FacetSearch;
