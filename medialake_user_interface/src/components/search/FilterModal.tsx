import React from "react";
import {
  useFilterModalOpen,
  useFilterModalDraft,
  useUIActions,
  useAggregations,
  useFacetsInfo,
  type CustomMetadataFieldDraft,
} from "../../stores/searchStore";
import { useSearchFields } from "@/api/hooks/useSearchFields";
import type { FieldInfo } from "@/api/hooks/useSearchFields";
import type { FieldAggregation } from "@/api/hooks/useSearch";
import {
  Box,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Typography,
  Divider,
  TextField,
  MenuItem,
  Select,
  FormControl,
  Button,
  IconButton,
  useTheme,
  ToggleButton,
  ToggleButtonGroup,
} from "@mui/material";
import { DateTimePicker } from "@mui/x-date-pickers/DateTimePicker";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDateFns } from "@mui/x-date-pickers/AdapterDateFns";
import {
  Close as CloseIcon,
  ImageOutlined as ImageIcon,
  VideocamOutlined as VideoIcon,
  AudiotrackOutlined as AudioIcon,
  AspectRatioOutlined as SizeIcon,
  DateRangeOutlined as DateIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { subDays } from "date-fns";
import { FILE_SIZE_UNITS } from "@/constants/fileSizeUnits";

// Date range options
const DATE_RANGE_OPTIONS = [
  { value: "24h", label: "Last 24 hours" },
  { value: "7d", label: "Last 7 days" },
  { value: "14d", label: "Last 14 days" },
  { value: "30d", label: "Last 30 days" },
];

// Media types with their associated extensions
const MEDIA_TYPES = [
  {
    key: "Image",
    icon: <ImageIcon />,
    extensions: ["jpg", "jpeg", "png", "gif", "svg", "webp", "tiff"],
  },
  {
    key: "Video",
    icon: <VideoIcon />,
    extensions: ["mp4", "mov", "avi", "wmv", "flv", "webm", "mkv"],
  },
  {
    key: "Audio",
    icon: <AudioIcon />,
    extensions: ["mp3", "wav", "ogg", "flac", "aac", "m4a"],
  },
];

export interface FilterModalProps {
  facetCounts?: {
    asset_types?: { buckets: Array<{ key: string; doc_count: number }> };
    file_extensions?: { buckets: Array<{ key: string; doc_count: number }> };
    file_size_ranges?: { buckets: Array<{ key: string; doc_count: number }> };
    ingestion_date?: { buckets: Array<{ key: string; doc_count: number }> };
  };
}

// Per-field filter control for custom metadata
const CustomFieldFilter: React.FC<{
  field: FieldInfo;
  fieldDraft: CustomMetadataFieldDraft;
  aggregation?: FieldAggregation;
  onUpdate: (partial: Partial<CustomMetadataFieldDraft>) => void;
  theme: ReturnType<typeof useTheme>;
}> = ({ field, fieldDraft, aggregation, onUpdate, theme }) => {
  const displayName = field.displayName || field.name;

  if (field.type === "number") {
    return (
      <Box sx={{ mb: 1.5 }}>
        <Typography variant="body2" sx={{ mb: 0.5, fontWeight: 500 }}>
          {displayName}
        </Typography>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <TextField
            type="number"
            size="small"
            value={fieldDraft.rangeMin ?? ""}
            onChange={(e) => onUpdate({ rangeMin: e.target.value || null })}
            placeholder="Min"
            sx={{ width: "100px" }}
          />
          <Typography variant="body2">to</Typography>
          <TextField
            type="number"
            size="small"
            value={fieldDraft.rangeMax ?? ""}
            onChange={(e) => onUpdate({ rangeMax: e.target.value || null })}
            placeholder="Max"
            sx={{ width: "100px" }}
          />
        </Box>
      </Box>
    );
  }

  if (field.type === "date") {
    return (
      <Box sx={{ mb: 1.5 }}>
        <Typography variant="body2" sx={{ mb: 0.5, fontWeight: 500 }}>
          {displayName}
        </Typography>
        <LocalizationProvider dateAdapter={AdapterDateFns}>
          <Box sx={{ display: "flex", gap: 1 }}>
            <DateTimePicker
              value={fieldDraft.rangeMin ? new Date(fieldDraft.rangeMin) : null}
              onChange={(v) => onUpdate({ rangeMin: v ? v.toISOString() : null })}
              format="yyyy/MM/dd hh:mm a"
              ampm
              closeOnSelect={false}
              slotProps={{
                textField: { size: "small", fullWidth: true, placeholder: "From" },
                actionBar: { actions: ["clear", "today", "accept"] },
              }}
            />
            <DateTimePicker
              value={fieldDraft.rangeMax ? new Date(fieldDraft.rangeMax) : null}
              onChange={(v) => onUpdate({ rangeMax: v ? v.toISOString() : null })}
              format="yyyy/MM/dd hh:mm a"
              ampm
              closeOnSelect={false}
              slotProps={{
                textField: { size: "small", fullWidth: true, placeholder: "To" },
                actionBar: { actions: ["clear", "today", "accept"] },
              }}
            />
          </Box>
        </LocalizationProvider>
      </Box>
    );
  }

  // Default: string type — facet toggles + free-text
  const buckets = aggregation?.buckets;
  return (
    <Box sx={{ mb: 1.5 }}>
      <Typography variant="body2" sx={{ mb: 0.5, fontWeight: 500 }}>
        {displayName}
      </Typography>
      {buckets && buckets.length > 0 ? (
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, mb: 1 }}>
          {buckets.map((bucket) => {
            const isSelected = fieldDraft.selectedFacetValues.includes(bucket.key);
            return (
              <Button
                key={bucket.key}
                size="small"
                variant={isSelected ? "contained" : "outlined"}
                color={isSelected ? "primary" : "inherit"}
                onClick={() => {
                  const updated = isSelected
                    ? fieldDraft.selectedFacetValues.filter((v) => v !== bucket.key)
                    : [...fieldDraft.selectedFacetValues, bucket.key];
                  onUpdate({ selectedFacetValues: updated });
                }}
                sx={{
                  minWidth: "60px",
                  height: "28px",
                  fontSize: "0.75rem",
                  textTransform: "none",
                  py: 0,
                  px: 1,
                  borderRadius: "14px",
                }}
              >
                {bucket.key} ({bucket.doc_count})
              </Button>
            );
          })}
        </Box>
      ) : (
        <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: "block" }}>
          No values found
        </Typography>
      )}
      <TextField
        size="small"
        fullWidth
        value={fieldDraft.textValue}
        onChange={(e) => onUpdate({ textValue: e.target.value })}
        placeholder={`${displayName} contains…`}
      />
    </Box>
  );
};

const FilterModal: React.FC<FilterModalProps> = () => {
  const { t } = useTranslation();
  const theme = useTheme();

  // Use store state and actions
  const isOpen = useFilterModalOpen();
  const draft = useFilterModalDraft();
  const { closeFilterModal, updateFilterModalDraft, applyFilterModalDraft, resetFilterModalDraft } =
    useUIActions();

  // Custom metadata data
  const { data: fieldsData } = useSearchFields();
  const aggregations = useAggregations();
  const facetsInfo = useFacetsInfo();
  const filterableFields = (fieldsData?.data?.availableFields ?? []).filter((f) => f.isFilterable);

  // Destructure draft state for easier access
  const {
    selectedMediaTypes,
    selectedExtensions,
    minSizeValue,
    maxSizeValue,
    sizeUnit,
    dateRangeOption,
    startDate,
    endDate,
    customMetadataFilters,
  } = draft;

  // Custom metadata helpers
  const getFieldDraft = (fieldName: string): CustomMetadataFieldDraft => {
    return (
      customMetadataFilters.find((d) => d.fieldName === fieldName) ?? {
        fieldName,
        type: "string",
        selectedFacetValues: [],
        textValue: "",
        rangeMin: null,
        rangeMax: null,
      }
    );
  };

  const updateFieldDraft = (
    fieldName: string,
    fieldType: string,
    partial: Partial<CustomMetadataFieldDraft>
  ) => {
    const existing = customMetadataFilters.find((d) => d.fieldName === fieldName);
    const updated = {
      ...getFieldDraft(fieldName),
      type: fieldType as CustomMetadataFieldDraft["type"],
      ...partial,
    };
    const newDrafts = existing
      ? customMetadataFilters.map((d) => (d.fieldName === fieldName ? updated : d))
      : [...customMetadataFilters, updated];
    updateFilterModalDraft({ customMetadataFilters: newDrafts });
  };

  const handleApply = () => {
    applyFilterModalDraft();
    closeFilterModal();
  };

  const handleReset = () => {
    resetFilterModalDraft();
    applyFilterModalDraft(); // Apply the reset immediately
  };

  const handleClose = () => {
    closeFilterModal();
  };

  const handleMediaTypeToggle = (type: string) => {
    const newSelectedMediaTypes = selectedMediaTypes.includes(type)
      ? selectedMediaTypes.filter((t) => t !== type)
      : [...selectedMediaTypes, type];

    updateFilterModalDraft({ selectedMediaTypes: newSelectedMediaTypes });
  };

  const handleExtensionToggle = (extension: string) => {
    const newSelectedExtensions = selectedExtensions.includes(extension)
      ? selectedExtensions.filter((e) => e !== extension)
      : [...selectedExtensions, extension];

    updateFilterModalDraft({ selectedExtensions: newSelectedExtensions });
  };

  const handleDateRangeChange = (value: string | null) => {
    if (value === null) return;

    const now = new Date();
    let newStartDate: Date | null = null;
    let newEndDate: Date | null = null;

    if (value === "24h") {
      newStartDate = subDays(now, 1);
      newEndDate = now;
    } else if (value === "7d") {
      newStartDate = subDays(now, 7);
      newEndDate = now;
    } else if (value === "14d") {
      newStartDate = subDays(now, 14);
      newEndDate = now;
    } else if (value === "30d") {
      newStartDate = subDays(now, 30);
      newEndDate = now;
    }

    updateFilterModalDraft({
      dateRangeOption: value,
      startDate: newStartDate,
      endDate: newEndDate,
    });
  };

  // Get available extensions from facet counts if available

  return (
    <Dialog
      open={isOpen}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          maxHeight: "80vh",
        },
      }}
    >
      <DialogTitle
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          pb: 1,
        }}
      >
        <Typography variant="h6">{t("search.filters.title", "Filter Results")}</Typography>
        <IconButton edge="end" color="inherit" onClick={handleClose} aria-label="close">
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <Divider />

      <DialogContent sx={{ p: 2 }}>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2.5 }}>
          {/* Media Type and Extensions Section */}
          <Box>
            <Typography
              variant="subtitle1"
              fontWeight="medium"
              sx={{ mb: 1.5, display: "flex", alignItems: "center" }}
            >
              <Box component="span" sx={{ mr: 1, display: "flex", alignItems: "center" }}>
                <ImageIcon fontSize="small" />
              </Box>
              Media Type and Extensions
            </Typography>

            {/* Media Types with Extensions */}
            {MEDIA_TYPES.map((mediaType) => (
              <Box key={mediaType.key} sx={{ mb: 1.5, display: "flex", flexDirection: "column" }}>
                <Box sx={{ display: "flex", alignItems: "center" }}>
                  {/* Media Type Button */}
                  <ToggleButton
                    value={mediaType.key}
                    selected={selectedMediaTypes.includes(mediaType.key)}
                    onChange={() => handleMediaTypeToggle(mediaType.key)}
                    aria-label={mediaType.key}
                    size="small"
                    color="primary"
                    sx={{
                      textTransform: "none",
                      minWidth: "80px",
                      display: "flex",
                      gap: 0.5,
                      px: 1.5,
                      py: 0.5,
                      borderRadius: "4px",
                      mr: 1,
                      "&.Mui-selected": {
                        backgroundColor: "primary.dark",
                        color: "primary.contrastText",
                        "&:hover": {
                          backgroundColor: "primary.dark",
                        },
                      },
                    }}
                  >
                    {mediaType.icon}
                    <Typography variant="body2" sx={{ color: "inherit" }}>
                      {mediaType.key}
                    </Typography>
                  </ToggleButton>

                  {/* Extensions */}
                  <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, ml: 1 }}>
                    {mediaType.extensions.map((ext) => {
                      const isSelected = selectedExtensions.includes(ext);

                      return (
                        <Button
                          key={ext}
                          size="small"
                          variant={isSelected ? "contained" : "outlined"}
                          color={isSelected ? "primary" : "inherit"}
                          onClick={() => handleExtensionToggle(ext)}
                          sx={{
                            minWidth: "60px",
                            height: "28px",
                            fontSize: "0.75rem",
                            textTransform: "uppercase",
                            py: 0,
                            px: 1,
                            borderRadius: "14px",
                            mb: 0.5,
                            opacity: 1,
                          }}
                        >
                          {ext}
                        </Button>
                      );
                    })}
                  </Box>
                </Box>
              </Box>
            ))}
          </Box>

          <Divider />

          {/* File Size Section */}
          <Box>
            <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
              <Typography
                variant="subtitle1"
                fontWeight="medium"
                sx={{ display: "flex", alignItems: "center" }}
              >
                <Box component="span" sx={{ mr: 1, display: "flex", alignItems: "center" }}>
                  <SizeIcon fontSize="small" />
                </Box>
                File Size
              </Typography>

              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <TextField
                  type="number"
                  size="small"
                  value={minSizeValue}
                  onChange={(e) => {
                    const newValue = e.target.value === "" ? "" : Number(e.target.value);
                    updateFilterModalDraft({ minSizeValue: newValue });
                  }}
                  inputProps={{ min: 0 }}
                  placeholder={t("search.filters.minSize", "Min")}
                  sx={{ width: "80px" }}
                />

                <Typography variant="body2" sx={{ mx: 0.5 }}>
                  to
                </Typography>

                <TextField
                  type="number"
                  size="small"
                  value={maxSizeValue}
                  onChange={(e) => {
                    const newValue = e.target.value === "" ? "" : Number(e.target.value);
                    updateFilterModalDraft({ maxSizeValue: newValue });
                  }}
                  inputProps={{ min: 0 }}
                  placeholder={t("search.filters.maxSize", "Max")}
                  sx={{ width: "80px" }}
                />

                <FormControl size="small" sx={{ width: "70px", ml: 0.5 }}>
                  <Select
                    value={sizeUnit}
                    onChange={(e) => {
                      updateFilterModalDraft({
                        sizeUnit: Number(e.target.value),
                      });
                    }}
                    displayEmpty
                  >
                    {FILE_SIZE_UNITS.map((unit) => (
                      <MenuItem key={unit.value} value={unit.value}>
                        {unit.label}
                      </MenuItem>
                    ))}
                  </Select>
                </FormControl>
              </Box>
            </Box>
          </Box>

          <Divider />

          {/* Date Created Section */}
          <Box>
            <Box sx={{ display: "flex", alignItems: "center", mb: 1.5 }}>
              <Typography
                variant="subtitle1"
                fontWeight="medium"
                sx={{ display: "flex", alignItems: "center", mr: 2 }}
              >
                <Box component="span" sx={{ mr: 1, display: "flex", alignItems: "center" }}>
                  <DateIcon fontSize="small" />
                </Box>
                Date Created
              </Typography>

              {/* Relative date options */}
              <ToggleButtonGroup
                value={dateRangeOption}
                exclusive
                onChange={(e, newValue) => handleDateRangeChange(newValue)}
                size="small"
                sx={{
                  "& .MuiToggleButton-root": {
                    textTransform: "none",
                    px: 1.5,
                    py: 0.5,
                    fontSize: "0.8125rem",
                    borderRadius: "4px",
                    mr: 0.5,
                  },
                }}
              >
                {DATE_RANGE_OPTIONS.map((option) => (
                  <ToggleButton key={option.value} value={option.value}>
                    {option.label}
                  </ToggleButton>
                ))}
              </ToggleButtonGroup>
            </Box>

            {/* Date pickers */}
            <LocalizationProvider dateAdapter={AdapterDateFns}>
              <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                <Box sx={{ flex: 1, minWidth: "140px" }}>
                  <Typography variant="body2" sx={{ mb: 0.5, fontSize: "0.75rem" }}>
                    {t("search.filters.fromDate", "From Date & Time")}
                  </Typography>
                  <DateTimePicker
                    value={startDate}
                    onChange={(newValue) => {
                      updateFilterModalDraft({ startDate: newValue });
                    }}
                    format="yyyy/MM/dd hh:mm a"
                    ampm={true}
                    closeOnSelect={false}
                    slotProps={{
                      textField: {
                        size: "small",
                        fullWidth: true,
                        InputProps: {
                          sx: {
                            "&.Mui-disabled": {
                              backgroundColor: theme.palette.action.disabledBackground,
                              opacity: 0.8,
                            },
                          },
                        },
                      },
                      actionBar: {
                        actions: ["clear", "today", "accept"],
                      },
                      layout: {
                        sx: {
                          "& .MuiPickersLayout-contentWrapper": {
                            backgroundColor: theme.palette.background.paper,
                          },
                        },
                      },
                    }}
                  />
                </Box>

                <Box sx={{ flex: 1, minWidth: "140px" }}>
                  <Typography variant="body2" sx={{ mb: 0.5, fontSize: "0.75rem" }}>
                    {t("search.filters.toDate", "To Date & Time")}
                  </Typography>
                  <DateTimePicker
                    value={endDate}
                    onChange={(newValue) => {
                      updateFilterModalDraft({ endDate: newValue });
                    }}
                    format="yyyy/MM/dd hh:mm a"
                    ampm={true}
                    closeOnSelect={false}
                    slotProps={{
                      textField: {
                        size: "small",
                        fullWidth: true,
                        InputProps: {
                          sx: {
                            "&.Mui-disabled": {
                              backgroundColor: theme.palette.action.disabledBackground,
                              opacity: 0.8,
                            },
                          },
                        },
                      },
                      actionBar: {
                        actions: ["clear", "today", "accept"],
                      },
                      layout: {
                        sx: {
                          "& .MuiPickersLayout-contentWrapper": {
                            backgroundColor: theme.palette.background.paper,
                          },
                        },
                      },
                    }}
                  />
                </Box>
              </Box>
            </LocalizationProvider>
          </Box>

          {/* Custom Metadata Section */}
          {filterableFields.length > 0 && (
            <>
              <Divider />
              <Box
                sx={{
                  background: "#fafbff",
                  border: "1px solid #e0e8f5",
                  borderRadius: 1.5,
                  p: 1.5,
                }}
              >
                <Typography variant="subtitle2" color="primary" sx={{ mb: 1.5 }}>
                  ⚙ Custom Metadata
                </Typography>

                {filterableFields.map((field) => (
                  <CustomFieldFilter
                    key={field.name}
                    field={field}
                    fieldDraft={getFieldDraft(field.name)}
                    aggregation={aggregations[field.name]}
                    onUpdate={(partial) => updateFieldDraft(field.name, field.type, partial)}
                    theme={theme}
                  />
                ))}

                {facetsInfo?.limited && (
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ mt: 1, display: "block" }}
                  >
                    Some fields may not show suggested values
                  </Typography>
                )}
              </Box>
            </>
          )}
        </Box>
      </DialogContent>

      <Divider />

      <DialogActions sx={{ p: 2, justifyContent: "space-between" }}>
        <Button onClick={handleReset} variant="outlined" size="small">
          {t("search.filters.reset", "Reset")}
        </Button>
        <Button onClick={handleApply} variant="contained" size="small">
          {t("search.filters.apply", "Apply Filters")}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default FilterModal;
