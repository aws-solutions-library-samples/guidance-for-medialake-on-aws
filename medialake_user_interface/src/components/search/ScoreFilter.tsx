import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Slider,
  Input,
  Paper,
  Chip,
  Tooltip,
  IconButton
} from '@mui/material';
import FilterListIcon from '@mui/icons-material/FilterList';
import ClearIcon from '@mui/icons-material/Clear';

interface ScoreFilterProps {
  value: number;
  onChange: (value: number) => void;
  onClear?: () => void;
  disabled?: boolean;
  showClearButton?: boolean;
  label?: string;
  totalResults?: number;
  filteredResults?: number;
}

const ScoreFilter: React.FC<ScoreFilterProps> = ({
  value,
  onChange,
  onClear,
  disabled = false,
  showClearButton = true,
  label = 'Score Filter',
  totalResults,
  filteredResults
}) => {
  const [inputValue, setInputValue] = useState(value.toString());
  const [isInputFocused, setIsInputFocused] = useState(false);

  // Update input value when prop changes
  useEffect(() => {
    if (!isInputFocused) {
      setInputValue(value.toFixed(3));
    }
  }, [value, isInputFocused]);

  const handleSliderChange = (_: Event, newValue: number | number[]) => {
    const numValue = Array.isArray(newValue) ? newValue[0] : newValue;
    onChange(numValue);
    setInputValue(numValue.toFixed(3));
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const valStr = e.target.value.replace(',', '.');
    
    // Allow empty string, single dot, or valid decimal numbers
    if (valStr === '' || valStr === '.' || /^\d*(\.\d{0,3})?$/.test(valStr)) {
      setInputValue(valStr);
      
      const numValue = parseFloat(valStr);
      if (!isNaN(numValue) && numValue >= 0 && numValue <= 1) {
        onChange(numValue);
      }
    }
  };

  const handleInputBlur = () => {
    setIsInputFocused(false);
    
    if (inputValue === '' || inputValue === '.') {
      setInputValue('0.000');
      onChange(0);
      return;
    }
    
    const numValue = parseFloat(inputValue);
    if (!isNaN(numValue) && numValue >= 0 && numValue <= 1) {
      setInputValue(numValue.toFixed(3));
      onChange(numValue);
    } else {
      setInputValue(value.toFixed(3));
    }
  };

  const handleClear = () => {
    onChange(0);
    setInputValue('0.000');
    onClear?.();
  };

  return (
    <Paper
      elevation={value > 0 ? 3 : 1}
      sx={{
        p: 2,
        borderRadius: 2,
        border: '1px solid',
        borderColor: value > 0 ? 'primary.main' : 'divider',
        bgcolor: value > 0 ? 'primary.50' : 'background.paper',
        minWidth: 280,
        transition: 'all 0.2s ease-in-out',
        '&:hover': {
          elevation: value > 0 ? 4 : 2,
        }
      }}
      data-testid="score-filter"
    >
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <FilterListIcon color="primary" fontSize="small" />
          <Typography variant="subtitle2" fontWeight={500}>
            {label}
          </Typography>
        </Box>
        
        {showClearButton && value > 0 && (
          <Tooltip title="Clear filter">
            <IconButton
              size="small"
              onClick={handleClear}
              disabled={disabled}
              sx={{ color: 'text.secondary' }}
              aria-label="Clear filter"
              data-testid="score-filter-clear"
            >
              <ClearIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        )}
      </Box>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
        <Slider
          value={value}
          min={0}
          max={1}
          step={0.001}
          onChange={handleSliderChange}
          disabled={disabled}
          valueLabelDisplay="auto"
          valueLabelFormat={(value) => value.toFixed(3)}
          color={filteredResults !== undefined && totalResults !== undefined && filteredResults === 0 && totalResults > 0 ? "warning" : "primary"}
          sx={{
            flexGrow: 1,
            '& .MuiSlider-thumb': {
              width: 16,
              height: 16,
            },
            '& .MuiSlider-track': {
              height: 4,
            },
            '& .MuiSlider-rail': {
              height: 4,
            }
          }}
        />
        
        <Input
          value={inputValue}
          onChange={handleInputChange}
          onBlur={handleInputBlur}
          onFocus={() => setIsInputFocused(true)}
          disabled={disabled}
          inputProps={{
            inputMode: 'decimal',
            'aria-labelledby': 'score-filter-input',
            'data-testid': 'score-filter-input',
            style: { 
              width: 70, 
              fontSize: '0.875rem', 
              padding: '4px 8px', 
              textAlign: 'center',
              borderRadius: '4px',
              border: '1px solid',
              borderColor: 'divider'
            }
          }}
          type="text"
          size="small"
          sx={{
            '& input': {
              textAlign: 'center',
              fontWeight: 500,
              fontSize: '0.875rem'
            }
          }}
        />
      </Box>

      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="caption" color="text.secondary">
          Min: 0.000
        </Typography>
        <Typography variant="caption" color="text.secondary">
          Max: 1.000
        </Typography>
      </Box>

      {value > 0 && (
        <Box sx={{ mt: 1 }}>
          <Chip
            label={`Showing results with score ≥ ${value.toFixed(3)}`}
            size="small"
            color={filteredResults !== undefined && totalResults !== undefined && filteredResults === 0 && totalResults > 0 ? "warning" : "primary"}
            variant="outlined"
            sx={{ fontSize: '0.75rem' }}
          />
          {totalResults !== undefined && filteredResults !== undefined && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
              {filteredResults} of {totalResults} results shown
              {totalResults > filteredResults && (
                <span style={{ color: 'warning.main' }}>
                  {' '}({totalResults - filteredResults} filtered out)
                </span>
              )}
              {filteredResults === 0 && totalResults > 0 && (
                <span style={{ color: 'error.main', fontWeight: 500 }}>
                  {' '}- No results match this filter!
                </span>
              )}
            </Typography>
          )}
        </Box>
      )}
    </Paper>
  );
};

export default ScoreFilter; 