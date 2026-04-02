import React from "react";
import {
  useFilterModalOpen,
  useFilterModalDraft,
  useUIActions,
  useAggregations,
  useFacetsInfo,
  useSemanticSearch,
  type CustomMetadataFieldDraft,
} from "../../stores/searchStore";
import { useSearchFields } from "@/api/hooks/useSearchFields";
import { useSearchFieldValues, useRefreshFieldValues } from "@/api/hooks/useSearchFieldValues";
import { useSemanticSearchStatus } from "@/features/settings/system/hooks/useSystemSettings";
import type { FieldInfo } from "@/api/hooks/useSearchFields";
import type { FieldAggregation, FacetBucket } from "@/api/hooks/useSearch";
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
  Autocomplete,
  Chip,
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
  eagerBuckets?: FacetBucket[];
  onUpdate: (partial: Partial<CustomMetadataFieldDraft>) => void;
  theme: ReturnType<typeof useTheme>;
}> = ({ field, fieldDraft, aggregation, eagerBuckets, onUpdate, theme }) => {
  const { t } = useTranslation();
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
              value={(() => {
                const d = fieldDraft.rangeMin ? new Date(fieldDraft.rangeMin) : null;
                return d && !isNaN(d.getTime()) ? d : null;
              })()}
              onChange={(v) =>
                onUpdate({ rangeMin: v && !isNaN(v.getTime()) ? v.toISOString() : null })
              }
              format="yyyy/MM/dd hh:mm a"
              ampm
              closeOnSelect={false}
              slotProps={{
                textField: { size: "small", fullWidth: true, placeholder: "From" },
                actionBar: { actions: ["clear", "today", "accept"] },
              }}
            />
            <DateTimePicker
              value={(() => {
                const d = fieldDraft.rangeMax ? new Date(fieldDraft.rangeMax) : null;
                return d && !isNaN(d.getTime()) ? d : null;
              })()}
              onChange={(v) =>
                onUpdate({ rangeMax: v && !isNaN(v.getTime()) ? v.toISOString() : null })
              }
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

  // Default: string type — autocomplete dropdown with doc counts
  const buckets = aggregation?.buckets;
  const allValues = React.useMemo(() => {
    const predefined = field.predefinedValues ?? [];
    const eager = eagerBuckets ?? [];
    const liveBuckets = buckets ?? [];

    // Build a map from eager buckets (already have doc_count from the index)
    const eagerMap = new Map(eager.map((b) => [b.key, b.doc_count]));

    // Build a map from live search aggregation buckets (scoped to current query)
    const liveMap = new Map(liveBuckets.map((b) => [b.key, b.doc_count]));

    // Determine the base set of known values.
    // Priority: predefined list > eager buckets > empty.
    // When we have eager buckets with counts, use those as the baseline so
    // the filter shows counts even before a search is performed.
    const baseKeys =
      predefined.length > 0 ? predefined : eager.length > 0 ? eager.map((b) => b.key) : [];

    if (baseKeys.length === 0) return liveBuckets;

    // Merge: for each base value, prefer the live count (scoped to current
    // search) when available, fall back to the eager count (global index
    // count), then 0.
    const merged: FacetBucket[] = baseKeys.map((val) => ({
      key: val,
      doc_count: liveMap.get(val) ?? eagerMap.get(val) ?? 0,
    }));

    // Append any live buckets that aren't already in the base set
    const baseSet = new Set(baseKeys);
    for (const bucket of liveBuckets) {
      if (!baseSet.has(bucket.key)) {
        merged.push(bucket);
      }
    }
    return merged;
  }, [buckets, field.predefinedValues, eagerBuckets]);

  // Selected option objects for the Autocomplete value
  const selectedOptions = React.useMemo(
    () => allValues.filter((v) => fieldDraft.selectedFacetValues.includes(v.key)),
    [allValues, fieldDraft.selectedFacetValues]
  );

  return (
    <Box sx={{ mb: 1.5 }}>
      <Autocomplete
        multiple
        size="small"
        options={allValues}
        value={selectedOptions}
        getOptionLabel={(option) => option.key}
        isOptionEqualToValue={(option, value) => option.key === value.key}
        onChange={(_, newValue) => {
          onUpdate({ selectedFacetValues: newValue.map((v) => v.key) });
        }}
        renderOption={(props, option) => {
          const { key, ...rest } = props;
          return (
            <li key={key} {...rest}>
              <Box sx={{ display: "flex", justifyContent: "space-between", width: "100%" }}>
                <Typography variant="body2">{option.key}</Typography>
                <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                  ({option.doc_count})
                </Typography>
              </Box>
            </li>
          );
        }}
        renderTags={(value, getTagProps) =>
          value.map((option, index) => {
            const { key, ...rest } = getTagProps({ index });
            return (
              <Chip
                key={key}
                label={`${option.key} (${option.doc_count})`}
                size="small"
                {...rest}
              />
            );
          })
        }
        renderInput={(params) => (
          <TextField
            {...params}
            label={displayName}
            placeholder={selectedOptions.length === 0 ? `Filter by ${displayName}…` : ""}
          />
        )}
        noOptionsText={t("search.filters.noValuesFound", "No values found")}
        sx={{ minWidth: 200 }}
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
  const { data: fieldValuesMap } = useSearchFieldValues();
  const refreshFieldValues = useRefreshFieldValues();
  const aggregations = useAggregations();
  const facetsInfo = useFacetsInfo();
  const isSemantic = useSemanticSearch();
  const { providerData } = useSemanticSearchStatus();
  const isCoactiveProvider = providerData?.data?.searchProvider?.type === "coactive";

  // Background-refresh the eager field values each time the modal opens so
  // the user sees fresh counts while the cached data is shown instantly.
  React.useEffect(() => {
    if (isOpen) {
      refreshFieldValues();
    }
  }, [isOpen, refreshFieldValues]);

  // Hide custom metadata filters when Coactive provider is active with semantic/hybrid search
  const hideCustomFilters = isCoactiveProvider && isSemantic;
  const filterableFields = hideCustomFilters
    ? []
    : (fieldsData?.data?.availableFields ?? []).filter((f) => f.isFilterable && !f.isDefault);

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
                  background: theme.palette.action.hover,
                  border: `1px solid ${theme.palette.divider}`,
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
                    eagerBuckets={fieldValuesMap?.[field.name]}
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
