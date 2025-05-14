import React, { useState, useEffect } from 'react';
import { FacetFilters } from '../../types/facetSearch';
import {
  Box,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Typography,
  Divider,
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
  Grid,
  Radio,
  RadioGroup,
  InputAdornment,
  ToggleButton,
  ToggleButtonGroup
} from '@mui/material';
import { DateTimePicker } from '@mui/x-date-pickers/DateTimePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import {
  Close as CloseIcon,
  ImageOutlined as ImageIcon,
  VideocamOutlined as VideoIcon,
  AudiotrackOutlined as AudioIcon,
  AspectRatioOutlined as SizeIcon,
  DateRangeOutlined as DateIcon
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { addDays, subDays, startOfDay } from 'date-fns';

// File size units for conversion
const FILE_SIZE_UNITS = [
  { value: 1, label: 'B' },
  { value: 1024, label: 'KB' },
  { value: 1024 * 1024, label: 'MB' },
  { value: 1024 * 1024 * 1024, label: 'GB' }
];

// Date range options
const DATE_RANGE_OPTIONS = [
  { value: '24h', label: 'Last 24 hours' },
  { value: '7d', label: 'Last 7 days' },
  { value: '14d', label: 'Last 14 days' },
  { value: '30d', label: 'Last 30 days' }
];

// Media types with their associated extensions
const MEDIA_TYPES = [
  { 
    key: 'Image', 
    icon: <ImageIcon />,
    extensions: ['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp', 'tiff']
  },
  { 
    key: 'Video', 
    icon: <VideoIcon />,
    extensions: ['mp4', 'mov', 'avi', 'wmv', 'flv', 'webm', 'mkv']
  },
  { 
    key: 'Audio', 
    icon: <AudioIcon />,
    extensions: ['mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a']
  }
];

export interface FilterModalProps {
  open: boolean;
  onClose: () => void;
  onApplyFilters: (filters: FacetFilters) => void;
  facetCounts?: {
    asset_types?: { buckets: Array<{ key: string; doc_count: number }> };
    file_extensions?: { buckets: Array<{ key: string; doc_count: number }> };
    file_size_ranges?: { buckets: Array<{ key: string; doc_count: number }> };
    ingestion_date?: { buckets: Array<{ key: string; doc_count: number }> };
  };
  activeFilters?: FacetFilters;
}

const FilterModal: React.FC<FilterModalProps> = ({
  open,
  onClose,
  onApplyFilters,
  facetCounts,
  activeFilters = {}
}) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const [filters, setFilters] = useState<FacetFilters>(activeFilters);
  
  // State for media types and extensions
  const [selectedMediaTypes, setSelectedMediaTypes] = useState<string[]>([]);
  const [selectedExtensions, setSelectedExtensions] = useState<string[]>([]);
  
  // State for file size inputs
  const [minSizeValue, setMinSizeValue] = useState<number | ''>('');
  const [maxSizeValue, setMaxSizeValue] = useState<number | ''>('');
  const [sizeUnit, setSizeUnit] = useState<number>(1024 * 1024); // Default to MB
  // Removed slider-related state
  
  // State for date range
  const [dateRangeOption, setDateRangeOption] = useState<string | null>(null); // Default to null so no button is selected
  const [startDate, setStartDate] = useState<Date | null>(
    filters.ingested_date_gte ? new Date(filters.ingested_date_gte) : null
  );
  const [endDate, setEndDate] = useState<Date | null>(
    filters.ingested_date_lte ? new Date(filters.ingested_date_lte) : null
  );

  // Initialize state from active filters when the modal opens
  useEffect(() => {
    if (open) {
      setFilters(activeFilters);
      
      // Initialize media types - handle comma-separated list
      if (activeFilters.type) {
        setSelectedMediaTypes(activeFilters.type.split(','));
      } else {
        setSelectedMediaTypes([]);
      }
      
      // Initialize extensions - handle comma-separated list
      if (activeFilters.extension) {
        setSelectedExtensions(activeFilters.extension.split(','));
      } else {
        setSelectedExtensions([]);
      }
      
      // Initialize file size
      if (activeFilters.asset_size_gte !== undefined) {
        // Find appropriate unit for display
        const { value, unit } = convertBytesToDisplayUnit(activeFilters.asset_size_gte);
        setMinSizeValue(value);
        setSizeUnit(unit);
      } else {
        setMinSizeValue('');
      }
      
      if (activeFilters.asset_size_lte !== undefined) {
        // Find appropriate unit for display
        const { value, unit } = convertBytesToDisplayUnit(activeFilters.asset_size_lte);
        setMaxSizeValue(value);
        if (activeFilters.asset_size_gte === undefined) {
          setSizeUnit(unit);
        }
      } else {
        setMaxSizeValue('');
      }
      
      // Initialize date range
      if (activeFilters.date_range_option) {
        // If we have a stored date range option, use it
        setDateRangeOption(activeFilters.date_range_option);
        
        if (activeFilters.ingested_date_gte) {
          setStartDate(new Date(activeFilters.ingested_date_gte));
        }
        
        if (activeFilters.ingested_date_lte) {
          setEndDate(new Date(activeFilters.ingested_date_lte));
        }
      } else if (activeFilters.ingested_date_gte && activeFilters.ingested_date_lte) {
        // Try to determine the date range option from the dates
        const now = new Date();
        const startDateObj = new Date(activeFilters.ingested_date_gte);
        const endDateObj = new Date(activeFilters.ingested_date_lte);
        
        const daysDiff = Math.round((now.getTime() - startDateObj.getTime()) / (1000 * 60 * 60 * 24));
        
        if (daysDiff <= 1 && isSameDay(endDateObj, now)) {
          setDateRangeOption('24h');
        } else if (daysDiff <= 7 && isSameDay(endDateObj, now)) {
          setDateRangeOption('7d');
        } else if (daysDiff <= 14 && isSameDay(endDateObj, now)) {
          setDateRangeOption('14d');
        } else if (daysDiff <= 30 && isSameDay(endDateObj, now)) {
          setDateRangeOption('30d');
        } else {
          setDateRangeOption(null);
        }
        
        setStartDate(startDateObj);
        setEndDate(endDateObj);
      } else {
        // Don't set default values when there are no active filters
        setDateRangeOption(null);
        setStartDate(null);
        setEndDate(null);
      }
    }
  }, [open, activeFilters]);

  // Helper function to check if two dates are the same day
  const isSameDay = (date1: Date, date2: Date) => {
    return (
      date1.getFullYear() === date2.getFullYear() &&
      date1.getMonth() === date2.getMonth() &&
      date1.getDate() === date2.getDate()
    );
  };

  // Helper function to convert bytes to appropriate unit for display
  const convertBytesToDisplayUnit = (bytes: number) => {
    if (bytes >= FILE_SIZE_UNITS[3].value) {
      return { value: bytes / FILE_SIZE_UNITS[3].value, unit: FILE_SIZE_UNITS[3].value };
    } else if (bytes >= FILE_SIZE_UNITS[2].value) {
      return { value: bytes / FILE_SIZE_UNITS[2].value, unit: FILE_SIZE_UNITS[2].value };
    } else if (bytes >= FILE_SIZE_UNITS[1].value) {
      return { value: bytes / FILE_SIZE_UNITS[1].value, unit: FILE_SIZE_UNITS[1].value };
    } else {
      return { value: bytes, unit: FILE_SIZE_UNITS[0].value };
    }
  };

  // Helper function to apply filters with conversions
  const applyFiltersWithConversions = () => {
    let updatedFilters: FacetFilters = {};
    
    // Apply media type filters - now supports multiple types
    if (selectedMediaTypes.length > 0) {
      updatedFilters.type = selectedMediaTypes.join(',');
    }
    
    // Apply extension filters - now supports multiple extensions
    if (selectedExtensions.length > 0) {
      updatedFilters.extension = selectedExtensions.join(',');
    }
    
    // Convert size inputs to bytes for API
    if (minSizeValue !== '') {
      updatedFilters.asset_size_gte = Number(minSizeValue) * sizeUnit;
    }
    
    if (maxSizeValue !== '') {
      updatedFilters.asset_size_lte = Number(maxSizeValue) * sizeUnit;
    }
    
    // Store the selected date range option in the filters
    if (dateRangeOption !== null) {
      updatedFilters.date_range_option = dateRangeOption;
    }
    
    // Apply date range filters
    if (dateRangeOption === '24h') {
      const now = new Date();
      const yesterday = subDays(now, 1);
      updatedFilters.ingested_date_gte = startOfDay(yesterday).toISOString();
      updatedFilters.ingested_date_lte = now.toISOString();
    } else if (dateRangeOption === '7d') {
      const now = new Date();
      const lastWeek = subDays(now, 7);
      updatedFilters.ingested_date_gte = startOfDay(lastWeek).toISOString();
      updatedFilters.ingested_date_lte = now.toISOString();
    } else if (dateRangeOption === '14d') {
      const now = new Date();
      const lastTwoWeeks = subDays(now, 14);
      updatedFilters.ingested_date_gte = startOfDay(lastTwoWeeks).toISOString();
      updatedFilters.ingested_date_lte = now.toISOString();
    } else if (dateRangeOption === '30d') {
      const now = new Date();
      const lastMonth = subDays(now, 30);
      updatedFilters.ingested_date_gte = startOfDay(lastMonth).toISOString();
      updatedFilters.ingested_date_lte = now.toISOString();
    } else {
      // If no date range option is selected, use the date pickers
      if (startDate) {
        updatedFilters.ingested_date_gte = startDate.toISOString();
      }
      
      if (endDate) {
        updatedFilters.ingested_date_lte = endDate.toISOString();
      }
    }
    
    return updatedFilters;
  };

  const handleApply = () => {
    const updatedFilters = applyFiltersWithConversions();
    onApplyFilters(updatedFilters);
    onClose();
  };

  const handleReset = () => {
    setFilters({});
    setSelectedMediaTypes([]);
    setSelectedExtensions([]);
    setMinSizeValue('');
    setMaxSizeValue('');
    // Removed slider reset
    setDateRangeOption(null); // Set to null so no button is selected
    setStartDate(null);
    setEndDate(null);
    
    // Immediately apply the reset filters
    onApplyFilters({});
  };
  
  // Enhanced close handler to reset filters
  const handleClose = () => {
    handleReset(); // Reset all filters
    onClose(); // Close the modal
  };

  const handleMediaTypeToggle = (type: string) => {
    setSelectedMediaTypes(prev => {
      if (prev.includes(type)) {
        return prev.filter(t => t !== type);
      } else {
        return [...prev, type];
      }
    });
  };

  const handleExtensionToggle = (extension: string) => {
    setSelectedExtensions(prev => {
      if (prev.includes(extension)) {
        return prev.filter(e => e !== extension);
      } else {
        return [...prev, extension];
      }
    });
  };

  // Removed slider-related functions as per requirements

  const handleDateRangeChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value;
    setDateRangeOption(value);
    
    const now = new Date();
    
    if (value === '24h') {
      // Set to start of yesterday and end of today
      setStartDate(startOfDay(subDays(now, 1)));
      setEndDate(now);
    } else if (value === '7d') {
      // Set to start of 7 days ago and end of today
      setStartDate(startOfDay(subDays(now, 7)));
      setEndDate(now);
    } else if (value === '14d') {
      // Set to start of 14 days ago and end of today
      setStartDate(startOfDay(subDays(now, 14)));
      setEndDate(now);
    } else if (value === '30d') {
      // Set to start of 30 days ago and end of today
      setStartDate(startOfDay(subDays(now, 30)));
      setEndDate(now);
    }
  };

  // Get available extensions from facet counts if available
  const availableExtensions = facetCounts?.file_extensions?.buckets || [];
  
  // Helper function to check if an extension is available in facet counts
  const isExtensionAvailable = (ext: string) => {
    return availableExtensions.some(e => e.key === ext);
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 2,
          maxHeight: '80vh'
        }
      }}
    >
      <DialogTitle sx={{ 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        pb: 1
      }}>
        <Typography variant="h6">{t('search.filters.title', 'Filter Results')}</Typography>
        <IconButton edge="end" color="inherit" onClick={handleClose} aria-label="close">
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      
      <Divider />
      
      <DialogContent sx={{ p: 2 }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
          {/* Media Type and Extensions Section - Collapsed and more compact */}
          <Box>
            <Typography variant="subtitle1" fontWeight="medium" sx={{ mb: 1.5, display: 'flex', alignItems: 'center' }}>
              <Box component="span" sx={{ mr: 1, display: 'flex', alignItems: 'center' }}>
                <ImageIcon fontSize="small" />
              </Box>
              Media Type and Extensions
            </Typography>
            
            {/* Media Types with Extensions directly to the right */}
            {MEDIA_TYPES.map((mediaType) => (
              <Box key={mediaType.key} sx={{ mb: 1.5, display: 'flex', flexDirection: 'column' }}>
                <Box sx={{ display: 'flex', alignItems: 'center' }}>
                  {/* Media Type Button */}
                  <ToggleButton
                    value={mediaType.key}
                    selected={selectedMediaTypes.includes(mediaType.key)}
                    onChange={() => handleMediaTypeToggle(mediaType.key)}
                    aria-label={mediaType.key}
                    size="small"
                    color="primary"
                    sx={{
                      textTransform: 'none',
                      minWidth: '80px',
                      display: 'flex',
                      gap: 0.5,
                      px: 1.5,
                      py: 0.5,
                      borderRadius: '4px',
                      mr: 1
                    }}
                  >
                    {mediaType.icon}
                    <Typography variant="body2">{mediaType.key}</Typography>
                  </ToggleButton>
                  
                  {/* Extensions directly to the right of type button */}
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, ml: 1 }}>
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
                            minWidth: '60px',
                            height: '28px',
                            fontSize: '0.75rem',
                            textTransform: 'lowercase',
                            py: 0,
                            px: 1,
                            borderRadius: '14px',
                            mb: 0.5,
                            opacity: 1 // Fully opaque
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
          
          {/* File Size Section - Without slider, label and inputs on same line */}
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Typography variant="subtitle1" fontWeight="medium" sx={{ display: 'flex', alignItems: 'center' }}>
                <Box component="span" sx={{ mr: 1, display: 'flex', alignItems: 'center' }}>
                  <SizeIcon fontSize="small" />
                </Box>
                File Size
              </Typography>
              
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <TextField
                type="number"
                size="small"
                value={minSizeValue}
                onChange={(e) => {
                  const newValue = e.target.value === '' ? '' : Number(e.target.value);
                  setMinSizeValue(newValue);
                }}
                inputProps={{ min: 0 }}
                placeholder={t('search.filters.minSize', 'Min')}
                sx={{ width: '80px' }}
              />
              
              <Typography variant="body2" sx={{ mx: 0.5 }}>to</Typography>
              
              <TextField
                type="number"
                size="small"
                value={maxSizeValue}
                onChange={(e) => {
                  const newValue = e.target.value === '' ? '' : Number(e.target.value);
                  setMaxSizeValue(newValue);
                }}
                inputProps={{ min: 0 }}
                placeholder={t('search.filters.maxSize', 'Max')}
                sx={{ width: '80px' }}
              />
              
              <FormControl size="small" sx={{ width: '70px', ml: 0.5 }}>
                <Select
                  value={sizeUnit}
                  onChange={(e) => {
                    setSizeUnit(Number(e.target.value));
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
          
          {/* Date Created Section - With relative options on same line as label */}
          <Box>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
              <Typography variant="subtitle1" fontWeight="medium" sx={{ display: 'flex', alignItems: 'center', mr: 2 }}>
                <Box component="span" sx={{ mr: 1, display: 'flex', alignItems: 'center' }}>
                  <DateIcon fontSize="small" />
                </Box>
                Date Created
              </Typography>
              
              {/* Relative date options on the same line as the label */}
              <ToggleButtonGroup
                value={dateRangeOption}
                exclusive
                onChange={(e, newValue) => {
                  if (newValue !== null) {
                    setDateRangeOption(newValue);
                    
                    const now = new Date();
                    
                    if (newValue === '24h') {
                      setStartDate(startOfDay(subDays(now, 1)));
                      setEndDate(now);
                    } else if (newValue === '7d') {
                      setStartDate(startOfDay(subDays(now, 7)));
                      setEndDate(now);
                    } else if (newValue === '14d') {
                      setStartDate(startOfDay(subDays(now, 14)));
                      setEndDate(now);
                    } else if (newValue === '30d') {
                      setStartDate(startOfDay(subDays(now, 30)));
                      setEndDate(now);
                    }
                  }
                }}
                size="small"
                sx={{
                  '& .MuiToggleButton-root': {
                    textTransform: 'none',
                    px: 1.5,
                    py: 0.5,
                    fontSize: '0.8125rem',
                    borderRadius: '4px',
                    mr: 0.5
                  }
                }}
              >
                {DATE_RANGE_OPTIONS.map((option) => (
                  <ToggleButton
                    key={option.value}
                    value={option.value}
                  >
                    {option.label}
                  </ToggleButton>
                ))}
              </ToggleButtonGroup>
            </Box>
            
            {/* Date pickers with more compact layout */}
            <LocalizationProvider dateAdapter={AdapterDateFns}>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                <Box sx={{ flex: 1, minWidth: '140px' }}>
                  <Typography variant="body2" sx={{ mb: 0.5, fontSize: '0.75rem' }}>
                    {t('search.filters.fromDate', 'From Date & Time')}
                  </Typography>
                  <DateTimePicker
                    value={startDate}
                    clearable={true}
                    onChange={(newValue) => {
                      setStartDate(newValue);
                      // Update date range option based on selected date
                      if (newValue) {
                        // No need to switch to custom range as it's been removed
                      }
                    }}
                    format="yyyy/MM/dd hh:mm a"
                    ampm={true}
                    closeOnSelect={false}
                    slotProps={{
                      textField: {
                        size: 'small',
                        fullWidth: true,
                        InputProps: {
                          sx: {
                            '&.Mui-disabled': {
                              backgroundColor: theme.palette.action.disabledBackground,
                              opacity: 0.8
                            }
                          }
                        }
                      },
                      actionBar: {
                        actions: ['clear', 'today', 'accept']
                      },
                      layout: {
                        sx: {
                          '& .MuiPickersLayout-contentWrapper': {
                            backgroundColor: theme.palette.background.paper
                          }
                        }
                      }
                    }}
                  />
                </Box>
                
                <Box sx={{ flex: 1, minWidth: '140px' }}>
                  <Typography variant="body2" sx={{ mb: 0.5, fontSize: '0.75rem' }}>
                    {t('search.filters.toDate', 'To Date & Time')}
                  </Typography>
                  <DateTimePicker
                    value={endDate}
                    clearable={true}
                    onChange={(newValue) => {
                      setEndDate(newValue);
                      // Update date range option based on selected date
                      if (newValue) {
                        // No need to switch to custom range as it's been removed
                      }
                    }}
                    format="yyyy/MM/dd hh:mm a"
                    ampm={true}
                    closeOnSelect={false}
                    slotProps={{
                      textField: {
                        size: 'small',
                        fullWidth: true,
                        InputProps: {
                          sx: {
                            '&.Mui-disabled': {
                              backgroundColor: theme.palette.action.disabledBackground,
                              opacity: 0.8
                            }
                          }
                        }
                      },
                      actionBar: {
                        actions: ['clear', 'today', 'accept']
                      },
                      layout: {
                        sx: {
                          '& .MuiPickersLayout-contentWrapper': {
                            backgroundColor: theme.palette.background.paper
                          }
                        }
                      }
                    }}
                  />
                </Box>
              </Box>
            </LocalizationProvider>
          </Box>
        </Box>
      </DialogContent>
      
      <Divider />
      
      <DialogActions sx={{ p: 2, justifyContent: 'space-between' }}>
        <Button onClick={handleReset} variant="outlined" size="small">
          {t('search.filters.reset', 'Reset')}
        </Button>
        <Button onClick={handleApply} variant="contained" size="small">
          {t('search.filters.apply', 'Apply Filters')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default FilterModal;