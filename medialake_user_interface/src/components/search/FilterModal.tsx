import React from "react";
import { FacetFilters } from "../../types/facetSearch";
import {
  useFilterModalOpen,
  useFilterModalDraft,
  useUIActions,
} from "../../stores/searchStore";
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

// File size units for conversion
const FILE_SIZE_UNITS = [
  { value: 1, label: "B" },
  { value: 1024, label: "KB" },
  { value: 1024 * 1024, label: "MB" },
  { value: 1024 * 1024 * 1024, label: "GB" },
];

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

const FilterModal: React.FC<FilterModalProps> = ({ facetCounts }) => {
  const { t } = useTranslation();
  const theme = useTheme();

  // Use store state and actions
  const isOpen = useFilterModalOpen();
  const draft = useFilterModalDraft();
  const {
    closeFilterModal,
    updateFilterModalDraft,
    applyFilterModalDraft,
    resetFilterModalDraft,
  } = useUIActions();

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
  } = draft;

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
  const availableExtensions = facetCounts?.file_extensions?.buckets || [];

  return (
    <Dialog
      open={isOpen}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 2,
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
        <Typography variant="h6">
          {t("search.filters.title", "Filter Results")}
        </Typography>
        <IconButton
          edge="end"
          color="inherit"
          onClick={handleClose}
          aria-label="close"
        >
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
              <Box
                component="span"
                sx={{ mr: 1, display: "flex", alignItems: "center" }}
              >
                <ImageIcon fontSize="small" />
              </Box>
              Media Type and Extensions
            </Typography>

            {/* Media Types with Extensions */}
            {MEDIA_TYPES.map((mediaType) => (
              <Box
                key={mediaType.key}
                sx={{ mb: 1.5, display: "flex", flexDirection: "column" }}
              >
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
                        backgroundColor: "#1a4971",
                        color: "#ffffff",
                        "&:hover": {
                          backgroundColor: "#153d61",
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
                  <Box
                    sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, ml: 1 }}
                  >
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
                <Box
                  component="span"
                  sx={{ mr: 1, display: "flex", alignItems: "center" }}
                >
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
                    const newValue =
                      e.target.value === "" ? "" : Number(e.target.value);
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
                    const newValue =
                      e.target.value === "" ? "" : Number(e.target.value);
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
                <Box
                  component="span"
                  sx={{ mr: 1, display: "flex", alignItems: "center" }}
                >
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
                  <Typography
                    variant="body2"
                    sx={{ mb: 0.5, fontSize: "0.75rem" }}
                  >
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
                              backgroundColor:
                                theme.palette.action.disabledBackground,
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
                  <Typography
                    variant="body2"
                    sx={{ mb: 0.5, fontSize: "0.75rem" }}
                  >
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
                              backgroundColor:
                                theme.palette.action.disabledBackground,
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
