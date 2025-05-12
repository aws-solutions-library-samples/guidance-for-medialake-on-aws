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
  Slider,
  InputAdornment
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import {
  Close as CloseIcon,
  ImageOutlined as ImageIcon,
  VideocamOutlined as VideoIcon,
  AudiotrackOutlined as AudioIcon,
  InsertDriveFileOutlined as FileIcon,
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
  { value: 'any', label: 'Any time' },
  { value: '24h', label: 'Last 24 hours' },
  { value: '7d', label: 'Last 7 days' },
  { value: '30d', label: 'Last 30 days' },
  { value: 'custom', label: 'Custom range' }
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
  
  // State for media types
  const [selectedMediaTypes, setSelectedMediaTypes] = useState<string[]>([]);
  
  // State for file extensions
  const [selectedExtensions, setSelectedExtensions] = useState<string[]>([]);
  const [showAllExtensions, setShowAllExtensions] = useState(false);
  
  // State for file size inputs
  const [minSizeValue, setMinSizeValue] = useState<number | ''>('');
  const [minSizeUnit, setMinSizeUnit] = useState<number>(1024 * 1024); // Default to MB
  const [maxSizeValue, setMaxSizeValue] = useState<number | ''>('');
  const [maxSizeUnit, setMaxSizeUnit] = useState<number>(1024 * 1024); // Default to MB
  const [sizeSliderValue, setSizeSliderValue] = useState<number[]>([0, 100]);
  
  // State for date range
  const [dateRangeOption, setDateRangeOption] = useState('any');
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
      
      // Initialize media types
      if (activeFilters.type) {
        setSelectedMediaTypes([activeFilters.type]);
      } else {
        setSelectedMediaTypes([]);
      }
      
      // Initialize extensions
      if (activeFilters.extension) {
        setSelectedExtensions([activeFilters.extension]);
      } else {
        setSelectedExtensions([]);
      }
      
      // Initialize file size
      if (activeFilters.asset_size_gte !== undefined) {
        // Find appropriate unit for display
        const { value, unit } = convertBytesToDisplayUnit(activeFilters.asset_size_gte);
        setMinSizeValue(value);
        setMinSizeUnit(unit);
      } else {
        setMinSizeValue('');
      }
      
      if (activeFilters.asset_size_lte !== undefined) {
        // Find appropriate unit for display
        const { value, unit } = convertBytesToDisplayUnit(activeFilters.asset_size_lte);
        setMaxSizeValue(value);
        setMaxSizeUnit(unit);
      } else {
        setMaxSizeValue('');
      }
      
      // Initialize date range
      if (activeFilters.ingested_date_gte && activeFilters.ingested_date_lte) {
        // Check if it matches any predefined ranges
        const now = new Date();
        const startDateObj = new Date(activeFilters.ingested_date_gte);
        const endDateObj = new Date(activeFilters.ingested_date_lte);
        
        const daysDiff = Math.round((now.getTime() - startDateObj.getTime()) / (1000 * 60 * 60 * 24));
        
        if (daysDiff <= 1 && isSameDay(endDateObj, now)) {
          setDateRangeOption('24h');
        } else if (daysDiff <= 7 && isSameDay(endDateObj, now)) {
          setDateRangeOption('7d');
        } else if (daysDiff <= 30 && isSameDay(endDateObj, now)) {
          setDateRangeOption('30d');
        } else {
          setDateRangeOption('custom');
        }
        
        setStartDate(startDateObj);
        setEndDate(endDateObj);
      } else {
        setDateRangeOption('any');
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
    
    // Apply media type filters
    if (selectedMediaTypes.length === 1) {
      updatedFilters.type = selectedMediaTypes[0];
    }
    
    // Apply extension filters
    if (selectedExtensions.length === 1) {
      updatedFilters.extension = selectedExtensions[0];
    }
    
    // Convert size inputs to bytes for API
    if (minSizeValue !== '') {
      updatedFilters.asset_size_gte = Number(minSizeValue) * minSizeUnit;
    }
    
    if (maxSizeValue !== '') {
      updatedFilters.asset_size_lte = Number(maxSizeValue) * maxSizeUnit;
    }
    
    // Apply date range filters
    if (dateRangeOption === 'any') {
      // No date filters
    } else if (dateRangeOption === '24h') {
      const now = new Date();
      const yesterday = subDays(now, 1);
      updatedFilters.ingested_date_gte = startOfDay(yesterday).toISOString().split('T')[0];
      updatedFilters.ingested_date_lte = now.toISOString().split('T')[0];
    } else if (dateRangeOption === '7d') {
      const now = new Date();
      const lastWeek = subDays(now, 7);
      updatedFilters.ingested_date_gte = startOfDay(lastWeek).toISOString().split('T')[0];
      updatedFilters.ingested_date_lte = now.toISOString().split('T')[0];
    } else if (dateRangeOption === '30d') {
      const now = new Date();
      const lastMonth = subDays(now, 30);
      updatedFilters.ingested_date_gte = startOfDay(lastMonth).toISOString().split('T')[0];
      updatedFilters.ingested_date_lte = now.toISOString().split('T')[0];
    } else if (dateRangeOption === 'custom') {
      // Convert dates to ISO strings
      if (startDate) {
        updatedFilters.ingested_date_gte = startDate.toISOString().split('T')[0];
      }
      
      if (endDate) {
        updatedFilters.ingested_date_lte = endDate.toISOString().split('T')[0];
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
    setSizeSliderValue([0, 100]);
    setDateRangeOption('any');
    setStartDate(null);
    setEndDate(null);
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

  const handleSizeSliderChange = (event: Event, newValue: number | number[]) => {
    if (Array.isArray(newValue)) {
      setSizeSliderValue(newValue);
      
      // Update min/max size values based on slider
      // This is a simplified example - you would need to map the slider values to actual byte values
      const minBytes = mapSliderValueToBytes(newValue[0]);
      const maxBytes = mapSliderValueToBytes(newValue[1]);
      
      const minDisplay = convertBytesToDisplayUnit(minBytes);
      const maxDisplay = convertBytesToDisplayUnit(maxBytes);
      
      setMinSizeValue(minDisplay.value);
      setMinSizeUnit(minDisplay.unit);
      setMaxSizeValue(maxDisplay.value);
      setMaxSizeUnit(maxDisplay.unit);
    }
  };

  // Helper function to map slider value (0-100) to bytes
  const mapSliderValueToBytes = (sliderValue: number) => {
    // Example mapping: 0 = 0 bytes, 100 = 10GB
    // This is a simplified example - you would need to adjust based on your data
    const maxBytes = 10 * 1024 * 1024 * 1024; // 10GB
    return Math.round((sliderValue / 100) * maxBytes);
  };

  const handleDateRangeChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value;
    setDateRangeOption(value);
    
    const now = new Date();
    
    if (value === 'any') {
      setStartDate(null);
      setEndDate(null);
    } else if (value === '24h') {
      // Set to start of yesterday and end of today
      setStartDate(startOfDay(subDays(now, 1)));
      setEndDate(now);
    } else if (value === '7d') {
      // Set to start of 7 days ago and end of today
      setStartDate(startOfDay(subDays(now, 7)));
      setEndDate(now);
    } else if (value === '30d') {
      // Set to start of 30 days ago and end of today
      setStartDate(startOfDay(subDays(now, 30)));
      setEndDate(now);
    }
    // For 'custom', we keep the existing dates or let the user select them
  };

  // Group extensions by type for better organization
  const extensionsByType: Record<string, string[]> = {
    Image: ['jpg', 'jpeg', 'png', 'gif', 'svg', 'webp', 'tiff'],
    Video: ['mp4', 'mov', 'avi', 'wmv', 'flv', 'webm', 'mkv'],
    Audio: ['mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a'],
    Document: ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt']
  };

  // Get available types from facet counts if available
  const availableTypes = facetCounts?.asset_types?.buckets || [
    { key: 'Image', doc_count: 0 },
    { key: 'Video', doc_count: 0 },
    { key: 'Audio', doc_count: 0 },
    { key: 'Document', doc_count: 0 }
  ];

  // Get available extensions from facet counts if available
  const availableExtensions = facetCounts?.file_extensions?.buckets || [];
  
  // Limit displayed extensions unless "show more" is clicked
  const displayedExtensions = showAllExtensions 
    ? availableExtensions 
    : availableExtensions.slice(0, 12);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="md"
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
        <IconButton edge="end" color="inherit" onClick={onClose} aria-label="close">
          <CloseIcon />
        </IconButton>
      </DialogTitle>
      
      <Divider />
      
      <DialogContent sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {/* Media Type Section */}
          <Box>
            <Typography variant="subtitle1" fontWeight="medium" sx={{ mb: 1.5, display: 'flex', alignItems: 'center' }}>
              <Box component="span" sx={{ mr: 1, display: 'flex', alignItems: 'center' }}>
                <ImageIcon fontSize="small" />
              </Box>
              Media Type
            </Typography>
            <Grid container spacing={1}>
              {availableTypes.map((type) => (
                <Grid item xs={6} sm={3} key={type.key}>
                  <FormControlLabel
                    control={
                      <Checkbox
                        checked={selectedMediaTypes.includes(type.key)}
                        onChange={() => handleMediaTypeToggle(type.key)}
                        size="small"
                      />
                    }
                    label={
                      <Typography variant="body2">
                        {type.key} {type.doc_count > 0 && `(${type.doc_count})`}
                      </Typography>
                    }
                  />
                </Grid>
              ))}
            </Grid>
          </Box>
          
          <Divider />
          
          {/* Extension Section */}
          <Box>
            <Typography variant="subtitle1" fontWeight="medium" sx={{ mb: 1.5, display: 'flex', alignItems: 'center' }}>
              <Box component="span" sx={{ mr: 1, display: 'flex', alignItems: 'center' }}>
                <FileIcon fontSize="small" />
              </Box>
              Extension
            </Typography>
            <Stack direction="row" spacing={0.5} flexWrap="wrap" useFlexGap>
              {displayedExtensions.map((ext) => (
                <Chip
                  key={ext.key}
                  label={ext.key}
                  size="small"
                  onClick={() => handleExtensionToggle(ext.key)}
                  color={selectedExtensions.includes(ext.key) ? "primary" : "default"}
                  sx={{ mb: 0.5, mr: 0.5 }}
                />
              ))}
              {availableExtensions.length > 12 && (
                <Chip
                  label={showAllExtensions ? "Show less" : "+ More"}
                  size="small"
                  onClick={() => setShowAllExtensions(!showAllExtensions)}
                  variant="outlined"
                  sx={{ mb: 0.5, mr: 0.5 }}
                />
              )}
            </Stack>
          </Box>
          
          <Divider />
          
          {/* File Size Section */}
          <Box>
            <Typography variant="subtitle1" fontWeight="medium" sx={{ mb: 1.5, display: 'flex', alignItems: 'center' }}>
              <Box component="span" sx={{ mr: 1, display: 'flex', alignItems: 'center' }}>
                <SizeIcon fontSize="small" />
              </Box>
              File Size
            </Typography>
            
            <Box sx={{ px: 2, mb: 2 }}>
              <Slider
                value={sizeSliderValue}
                onChange={handleSizeSliderChange}
                valueLabelDisplay="auto"
                valueLabelFormat={(value) => {
                  const bytes = mapSliderValueToBytes(value);
                  const { value: displayValue, unit } = convertBytesToDisplayUnit(bytes);
                  const unitLabel = FILE_SIZE_UNITS.find(u => u.value === unit)?.label || 'B';
                  return `${displayValue.toFixed(1)} ${unitLabel}`;
                }}
              />
            </Box>
            
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <Typography variant="body2" sx={{ mb: 0.5 }}>
                  {t('search.filters.minSize', 'Minimum Size')}
                </Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <TextField
                    type="number"
                    size="small"
                    value={minSizeValue}
                    onChange={(e) => {
                      const newValue = e.target.value === '' ? '' : Number(e.target.value);
                      setMinSizeValue(newValue);
                    }}
                    inputProps={{ min: 0 }}
                    sx={{ flex: 1 }}
                  />
                  <FormControl size="small" sx={{ width: 70 }}>
                    <Select
                      value={minSizeUnit}
                      onChange={(e) => {
                        setMinSizeUnit(Number(e.target.value));
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
                <Typography variant="body2" sx={{ mb: 0.5 }}>
                  {t('search.filters.maxSize', 'Maximum Size')}
                </Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <TextField
                    type="number"
                    size="small"
                    value={maxSizeValue}
                    onChange={(e) => {
                      const newValue = e.target.value === '' ? '' : Number(e.target.value);
                      setMaxSizeValue(newValue);
                    }}
                    inputProps={{ min: 0 }}
                    sx={{ flex: 1 }}
                  />
                  <FormControl size="small" sx={{ width: 70 }}>
                    <Select
                      value={maxSizeUnit}
                      onChange={(e) => {
                        setMaxSizeUnit(Number(e.target.value));
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
          </Box>
          
          <Divider />
          
          {/* Date Created Section */}
          <Box>
            <Typography variant="subtitle1" fontWeight="medium" sx={{ mb: 1.5, display: 'flex', alignItems: 'center' }}>
              <Box component="span" sx={{ mr: 1, display: 'flex', alignItems: 'center' }}>
                <DateIcon fontSize="small" />
              </Box>
              Date Created
            </Typography>
            
            <RadioGroup
              value={dateRangeOption}
              onChange={handleDateRangeChange}
            >
              {DATE_RANGE_OPTIONS.map((option) => (
                <FormControlLabel
                  key={option.value}
                  value={option.value}
                  control={<Radio size="small" />}
                  label={<Typography variant="body2">{option.label}</Typography>}
                />
              ))}
            </RadioGroup>
            
            {/* Always show date pickers regardless of selected option */}
            <LocalizationProvider dateAdapter={AdapterDateFns}>
              <Grid container spacing={2} sx={{ mt: 1 }}>
                <Grid item xs={6}>
                  <Typography variant="body2" sx={{ mb: 0.5 }}>
                    {t('search.filters.fromDate', 'From Date')}
                  </Typography>
                  <DatePicker
                    value={startDate}
                    onChange={(newValue) => {
                      setStartDate(newValue);
                      // If user manually selects a date, switch to custom range
                      if (newValue && dateRangeOption !== 'custom') {
                        setDateRangeOption('custom');
                      }
                    }}
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
                      }
                    }}
                  />
                </Grid>
                
                <Grid item xs={6}>
                  <Typography variant="body2" sx={{ mb: 0.5 }}>
                    {t('search.filters.toDate', 'To Date')}
                  </Typography>
                  <DatePicker
                    value={endDate}
                    onChange={(newValue) => {
                      setEndDate(newValue);
                      // If user manually selects a date, switch to custom range
                      if (newValue && dateRangeOption !== 'custom') {
                        setDateRangeOption('custom');
                      }
                    }}
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
                      }
                    }}
                  />
                </Grid>
              </Grid>
            </LocalizationProvider>
          </Box>
        </Box>
      </DialogContent>
      
      <Divider />
      
      <DialogActions sx={{ p: 2, justifyContent: 'space-between' }}>
        <Button onClick={handleReset} variant="outlined">
          {t('search.filters.reset', 'Reset')}
        </Button>
        <Button onClick={handleApply} variant="contained">
          {t('search.filters.apply', 'Apply Filters')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default FilterModal;