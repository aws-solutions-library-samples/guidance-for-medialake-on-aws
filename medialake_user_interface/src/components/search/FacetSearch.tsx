import React, { useState } from 'react';
import {
  Box,
  Popover,
  Typography,
  Divider,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  FormGroup,
  FormControlLabel,
  Checkbox,
  TextField,
  MenuItem,
  Select,
  InputLabel,
  FormControl,
  Button,
  Chip,
  Stack,
  IconButton,
  useTheme
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import {
  ExpandMore as ExpandMoreIcon,
  FilterList as FilterListIcon,
  Clear as ClearIcon
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';

// File size units for conversion
const FILE_SIZE_UNITS = [
  { value: 1, label: 'B' },
  { value: 1024, label: 'KB' },
  { value: 1024 * 1024, label: 'MB' },
  { value: 1024 * 1024 * 1024, label: 'GB' }
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
}

export interface FacetFilters {
  type?: string;
  extension?: string;
  LargerThan?: number;
  asset_size_lte?: number;
  asset_size_gte?: number;
  ingested_date_lte?: string;
  ingested_date_gte?: string;
  filename?: string;
}

const FacetSearch: React.FC<FacetSearchProps> = ({
  onApplyFilters,
  facetCounts,
  activeFilters = {}
}) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const [anchorEl, setAnchorEl] = useState<HTMLButtonElement | null>(null);
  const [filters, setFilters] = useState<FacetFilters>(activeFilters);
  
  // State for file size inputs
  const [minSizeValue, setMinSizeValue] = useState<number | ''>('');
  const [minSizeUnit, setMinSizeUnit] = useState<number>(1024 * 1024); // Default to MB
  const [maxSizeValue, setMaxSizeValue] = useState<number | ''>('');
  const [maxSizeUnit, setMaxSizeUnit] = useState<number>(1024 * 1024); // Default to MB
  
  // State for date pickers
  const [startDate, setStartDate] = useState<Date | null>(
    filters.ingested_date_gte ? new Date(filters.ingested_date_gte) : null
  );
  const [endDate, setEndDate] = useState<Date | null>(
    filters.ingested_date_lte ? new Date(filters.ingested_date_lte) : null
  );

  // Count active filters
  const activeFilterCount = Object.values(activeFilters).filter(Boolean).length;

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleApply = () => {
    // Convert size inputs to bytes for API
    let updatedFilters = { ...filters };
    
    if (minSizeValue !== '') {
      updatedFilters.asset_size_gte = Number(minSizeValue) * minSizeUnit;
    }
    
    if (maxSizeValue !== '') {
      updatedFilters.asset_size_lte = Number(maxSizeValue) * maxSizeUnit;
    }
    
    // Convert dates to ISO strings
    if (startDate) {
      updatedFilters.ingested_date_gte = startDate.toISOString().split('T')[0];
    }
    
    if (endDate) {
      updatedFilters.ingested_date_lte = endDate.toISOString().split('T')[0];
    }
    
    onApplyFilters(updatedFilters);
    handleClose();
  };

  const handleClearFilters = () => {
    setFilters({});
    setMinSizeValue('');
    setMaxSizeValue('');
    setStartDate(null);
    setEndDate(null);
    onApplyFilters({});
    handleClose();
  };

  const handleTypeChange = (type: string) => {
    setFilters(prev => ({
      ...prev,
      type: prev.type === type ? undefined : type
    }));
  };

  const handleExtensionChange = (extension: string) => {
    setFilters(prev => ({
      ...prev,
      extension: prev.extension === extension ? undefined : extension
    }));
  };

  const handleFilenameChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setFilters(prev => ({
      ...prev,
      filename: event.target.value || undefined
    }));
  };

  const open = Boolean(anchorEl);
  const id = open ? 'facet-search-popover' : undefined;

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

  return (
    <>
      <IconButton
        aria-describedby={id}
        onClick={handleClick}
        size="small"
        sx={{
          position: 'relative',
          color: theme.palette.text.secondary,
        }}
      >
        <FilterListIcon />
        {activeFilterCount > 0 && (
          <Box
            sx={{
              position: 'absolute',
              top: -2,
              right: -2,
              backgroundColor: theme.palette.primary.main,
              color: theme.palette.primary.contrastText,
              borderRadius: '50%',
              width: 16,
              height: 16,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '0.75rem',
              fontWeight: 'bold',
            }}
          >
            {activeFilterCount}
          </Box>
        )}
      </IconButton>
      
      <Popover
        id={id}
        open={open}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
        PaperProps={{
          sx: {
            width: 320,
            maxHeight: 500,
            overflow: 'auto',
            mt: 1,
            p: 2
          }
        }}
      >
        <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="h6">{t('search.filters.title', 'Filters')}</Typography>
          <Button 
            size="small" 
            onClick={handleClearFilters}
            disabled={!activeFilterCount}
          >
            {t('search.filters.clearAll', 'Clear All')}
          </Button>
        </Box>

        {/* Media Type Filter */}
        <Accordion defaultExpanded>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography>{t('search.filters.mediaType', 'Media Type')}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <FormGroup>
              {availableTypes.map((type) => (
                <FormControlLabel
                  key={type.key}
                  control={
                    <Checkbox
                      checked={filters.type === type.key}
                      onChange={() => handleTypeChange(type.key)}
                      size="small"
                    />
                  }
                  label={
                    <Typography variant="body2">
                      {type.key} {type.doc_count > 0 && `(${type.doc_count})`}
                    </Typography>
                  }
                />
              ))}
            </FormGroup>
          </AccordionDetails>
        </Accordion>

        {/* File Extension Filter */}
        <Accordion>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography>{t('search.filters.fileExtension', 'File Extension')}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <FormGroup>
              {availableExtensions.length > 0 ? (
                availableExtensions.map((ext) => (
                  <FormControlLabel
                    key={ext.key}
                    control={
                      <Checkbox
                        checked={filters.extension === ext.key}
                        onChange={() => handleExtensionChange(ext.key)}
                        size="small"
                      />
                    }
                    label={
                      <Typography variant="body2">
                        {ext.key} ({ext.doc_count})
                      </Typography>
                    }
                  />
                ))
              ) : (
                Object.entries(extensionsByType).map(([type, extensions]) => (
                  <Box key={type} sx={{ mb: 2 }}>
                    <Typography variant="subtitle2" sx={{ mb: 1 }}>{type}</Typography>
                    <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                      {extensions.map(ext => (
                        <Chip
                          key={ext}
                          label={ext}
                          size="small"
                          onClick={() => handleExtensionChange(ext)}
                          color={filters.extension === ext ? "primary" : "default"}
                          sx={{ mb: 1 }}
                        />
                      ))}
                    </Stack>
                  </Box>
                ))
              )}
            </FormGroup>
          </AccordionDetails>
        </Accordion>

        {/* File Size Filter */}
        <Accordion>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography>{t('search.filters.fileSize', 'File Size')}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Box sx={{ mb: 2 }}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                {t('search.filters.minSize', 'Minimum Size')}
              </Typography>
              <Box sx={{ display: 'flex', gap: 1 }}>
                <TextField
                  type="number"
                  size="small"
                  value={minSizeValue}
                  onChange={(e) => setMinSizeValue(e.target.value === '' ? '' : Number(e.target.value))}
                  inputProps={{ min: 0 }}
                  sx={{ flex: 1 }}
                />
                <FormControl size="small" sx={{ width: 80 }}>
                  <Select
                    value={minSizeUnit}
                    onChange={(e) => setMinSizeUnit(Number(e.target.value))}
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
            
            <Box sx={{ mb: 2 }}>
              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                {t('search.filters.maxSize', 'Maximum Size')}
              </Typography>
              <Box sx={{ display: 'flex', gap: 1 }}>
                <TextField
                  type="number"
                  size="small"
                  value={maxSizeValue}
                  onChange={(e) => setMaxSizeValue(e.target.value === '' ? '' : Number(e.target.value))}
                  inputProps={{ min: 0 }}
                  sx={{ flex: 1 }}
                />
                <FormControl size="small" sx={{ width: 80 }}>
                  <Select
                    value={maxSizeUnit}
                    onChange={(e) => setMaxSizeUnit(Number(e.target.value))}
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
          </AccordionDetails>
        </Accordion>

        {/* Date Range Filter */}
        <Accordion>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography>{t('search.filters.dateRange', 'Date Range')}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <LocalizationProvider dateAdapter={AdapterDateFns}>
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  {t('search.filters.fromDate', 'From Date')}
                </Typography>
                <DatePicker
                  value={startDate}
                  onChange={(newValue) => setStartDate(newValue)}
                  slotProps={{ textField: { size: 'small', fullWidth: true } }}
                />
              </Box>
              
              <Box sx={{ mb: 2 }}>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  {t('search.filters.toDate', 'To Date')}
                </Typography>
                <DatePicker
                  value={endDate}
                  onChange={(newValue) => setEndDate(newValue)}
                  slotProps={{ textField: { size: 'small', fullWidth: true } }}
                />
              </Box>
            </LocalizationProvider>
          </AccordionDetails>
        </Accordion>

        {/* Filename Search */}
        <Accordion>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography>{t('search.filters.filename', 'Filename')}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <TextField
              fullWidth
              size="small"
              placeholder={t('search.filters.filenameSearch', 'Search by filename')}
              value={filters.filename || ''}
              onChange={handleFilenameChange}
            />
          </AccordionDetails>
        </Accordion>

        <Box sx={{ mt: 2, display: 'flex', justifyContent: 'flex-end' }}>
          <Button variant="contained" onClick={handleApply}>
            {t('search.filters.apply', 'Apply Filters')}
          </Button>
        </Box>
      </Popover>
    </>
  );
};

export default FacetSearch;