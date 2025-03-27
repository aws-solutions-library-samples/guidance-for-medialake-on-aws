import React, { useState } from 'react';
import {
  Box,
  Typography,
  ToggleButtonGroup,
  ToggleButton,
  IconButton,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Divider,
  FormControlLabel,
  Switch,
  Tooltip,
  useTheme,
  alpha,
  Paper
} from '@mui/material';
import {
  ViewModule as ViewModuleIcon,
  ViewList as ViewListIcon,
  Sort as SortIcon,
  FilterList as FilterListIcon,
  ViewColumn as ViewColumnIcon,
  CheckBox as CheckBoxIcon,
  CheckBoxOutlineBlank as CheckBoxOutlineBlankIcon,
  AspectRatio as AspectRatioIcon,
  Crop as CropIcon,
  ViewComfy as ViewComfyIcon,
  ViewCompact as ViewCompactIcon,
  ViewArray as ViewArrayIcon
} from '@mui/icons-material';
import { SortingState } from '@tanstack/react-table';

interface AssetViewControlsProps {
  viewMode: 'card' | 'table';
  onViewModeChange: (event: React.MouseEvent<HTMLElement>, newMode: 'card' | 'table' | null) => void;
  title: string | React.ReactNode;
  sorting: SortingState;
  sortOptions: { id: string; label: string }[];
  onSortChange: (columnId: string) => void;
  fields: { id: string; label: string; visible: boolean }[];
  onFieldToggle: (fieldId: string) => void;
  groupByType: boolean;
  onGroupByTypeChange: (checked: boolean) => void;
  cardSize: 'small' | 'medium' | 'large';
  onCardSizeChange: (size: 'small' | 'medium' | 'large') => void;
  aspectRatio: 'vertical' | 'square' | 'horizontal';
  onAspectRatioChange: (ratio: 'vertical' | 'square' | 'horizontal') => void;
  thumbnailScale: 'fit' | 'fill';
  onThumbnailScaleChange: (scale: 'fit' | 'fill') => void;
  showMetadata: boolean;
  onShowMetadataChange: (show: boolean) => void;
}

const AssetViewControls: React.FC<AssetViewControlsProps> = ({
  viewMode,
  onViewModeChange,
  title,
  sorting,
  sortOptions,
  onSortChange,
  fields,
  onFieldToggle,
  groupByType,
  onGroupByTypeChange,
  cardSize,
  onCardSizeChange,
  aspectRatio,
  onAspectRatioChange,
  thumbnailScale,
  onThumbnailScaleChange,
  showMetadata,
  onShowMetadataChange
}) => {
  const theme = useTheme();
  const [sortMenuAnchorEl, setSortMenuAnchorEl] = useState<null | HTMLElement>(null);
  const [fieldsMenuAnchorEl, setFieldsMenuAnchorEl] = useState<null | HTMLElement>(null);
  const [displayMenuAnchorEl, setDisplayMenuAnchorEl] = useState<null | HTMLElement>(null);

  const handleSortMenuOpen = (event: React.MouseEvent<HTMLButtonElement>) => {
    setSortMenuAnchorEl(event.currentTarget);
  };

  const handleSortMenuClose = () => {
    setSortMenuAnchorEl(null);
  };

  const handleFieldsMenuOpen = (event: React.MouseEvent<HTMLButtonElement>) => {
    setFieldsMenuAnchorEl(event.currentTarget);
  };

  const handleFieldsMenuClose = () => {
    setFieldsMenuAnchorEl(null);
  };

  const handleDisplayMenuOpen = (event: React.MouseEvent<HTMLButtonElement>) => {
    setDisplayMenuAnchorEl(event.currentTarget);
  };

  const handleDisplayMenuClose = () => {
    setDisplayMenuAnchorEl(null);
  };

  const handleSortOptionClick = (columnId: string) => {
    onSortChange(columnId);
    handleSortMenuClose();
  };

  const handleFieldToggle = (fieldId: string) => {
    onFieldToggle(fieldId);
  };

  const handleCardSizeChange = (size: 'small' | 'medium' | 'large') => {
    onCardSizeChange(size);
    handleDisplayMenuClose();
  };

  const handleAspectRatioChange = (ratio: 'vertical' | 'square' | 'horizontal') => {
    onAspectRatioChange(ratio);
    handleDisplayMenuClose();
  };

  const handleThumbnailScaleChange = (scale: 'fit' | 'fill') => {
    onThumbnailScaleChange(scale);
    handleDisplayMenuClose();
  };

  const handleShowMetadataChange = () => {
    onShowMetadataChange(!showMetadata);
    handleDisplayMenuClose();
  };

  const handleGroupByTypeChange = () => {
    onGroupByTypeChange(!groupByType);
    handleDisplayMenuClose();
  };

  return (
    <Paper
      elevation={0}
      sx={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        mb: 3,
        p: 2,
        borderRadius: 2,
        backgroundColor: theme => alpha(theme.palette.background.paper, 0.8),
        backdropFilter: 'blur(8px)',
        position: 'sticky',
        top: 0,
        zIndex: 20, // Higher z-index to ensure it stays above hovered cards
      }}
    >
      <Typography variant="h6" sx={{ fontWeight: 600 }}>
        {title}
      </Typography>

      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
        <Tooltip title="Sort">
          <IconButton onClick={handleSortMenuOpen} size="small">
            <SortIcon />
          </IconButton>
        </Tooltip>

        <Tooltip title="Display Options">
          <IconButton onClick={handleDisplayMenuOpen} size="small">
            <FilterListIcon />
          </IconButton>
        </Tooltip>

        <Tooltip title="Visible Fields">
          <IconButton onClick={handleFieldsMenuOpen} size="small">
            <ViewColumnIcon />
          </IconButton>
        </Tooltip>

        <Divider orientation="vertical" flexItem sx={{ mx: 1 }} />

        <ToggleButtonGroup
          value={viewMode}
          exclusive
          onChange={onViewModeChange}
          aria-label="view mode"
          size="small"
        >
          <ToggleButton value="card" aria-label="card view">
            <ViewModuleIcon fontSize="small" />
          </ToggleButton>
          <ToggleButton value="table" aria-label="table view">
            <ViewListIcon fontSize="small" />
          </ToggleButton>
        </ToggleButtonGroup>
      </Box>

      {/* Sort Menu */}
      <Menu
        anchorEl={sortMenuAnchorEl}
        open={Boolean(sortMenuAnchorEl)}
        onClose={handleSortMenuClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
      >
        {sortOptions.map((option) => {
          const isActive = sorting.some(sort => sort.id === option.id);
          const isDesc = sorting.some(sort => sort.id === option.id && sort.desc);
          
          return (
            <MenuItem
              key={option.id}
              onClick={() => handleSortOptionClick(option.id)}
              selected={isActive}
            >
              <ListItemText>
                {option.label} {isActive && (isDesc ? '↓' : '↑')}
              </ListItemText>
            </MenuItem>
          );
        })}
      </Menu>

      {/* Fields Menu */}
      <Menu
        anchorEl={fieldsMenuAnchorEl}
        open={Boolean(fieldsMenuAnchorEl)}
        onClose={handleFieldsMenuClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
      >
        {fields.map((field) => (
          <MenuItem key={field.id} onClick={() => handleFieldToggle(field.id)}>
            <ListItemIcon>
              {field.visible ? (
                <CheckBoxIcon fontSize="small" color="primary" />
              ) : (
                <CheckBoxOutlineBlankIcon fontSize="small" />
              )}
            </ListItemIcon>
            <ListItemText>{field.label}</ListItemText>
          </MenuItem>
        ))}
      </Menu>

      {/* Display Options Menu */}
      <Menu
        anchorEl={displayMenuAnchorEl}
        open={Boolean(displayMenuAnchorEl)}
        onClose={handleDisplayMenuClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
      >
        {viewMode === 'card' && (
          <>
            <MenuItem disabled>
              <Typography variant="subtitle2">Card Size</Typography>
            </MenuItem>
            <MenuItem onClick={() => handleCardSizeChange('small')}>
              <ListItemIcon>
                {cardSize === 'small' ? (
                  <CheckBoxIcon fontSize="small" color="primary" />
                ) : (
                  <CheckBoxOutlineBlankIcon fontSize="small" />
                )}
              </ListItemIcon>
              <ListItemText>Small</ListItemText>
            </MenuItem>
            <MenuItem onClick={() => handleCardSizeChange('medium')}>
              <ListItemIcon>
                {cardSize === 'medium' ? (
                  <CheckBoxIcon fontSize="small" color="primary" />
                ) : (
                  <CheckBoxOutlineBlankIcon fontSize="small" />
                )}
              </ListItemIcon>
              <ListItemText>Medium</ListItemText>
            </MenuItem>
            <MenuItem onClick={() => handleCardSizeChange('large')}>
              <ListItemIcon>
                {cardSize === 'large' ? (
                  <CheckBoxIcon fontSize="small" color="primary" />
                ) : (
                  <CheckBoxOutlineBlankIcon fontSize="small" />
                )}
              </ListItemIcon>
              <ListItemText>Large</ListItemText>
            </MenuItem>

            <Divider />

            <MenuItem disabled>
              <Typography variant="subtitle2">Aspect Ratio</Typography>
            </MenuItem>
            <MenuItem onClick={() => handleAspectRatioChange('vertical')}>
              <ListItemIcon>
                {aspectRatio === 'vertical' ? (
                  <CheckBoxIcon fontSize="small" color="primary" />
                ) : (
                  <CheckBoxOutlineBlankIcon fontSize="small" />
                )}
              </ListItemIcon>
              <ListItemText>Vertical</ListItemText>
            </MenuItem>
            <MenuItem onClick={() => handleAspectRatioChange('square')}>
              <ListItemIcon>
                {aspectRatio === 'square' ? (
                  <CheckBoxIcon fontSize="small" color="primary" />
                ) : (
                  <CheckBoxOutlineBlankIcon fontSize="small" />
                )}
              </ListItemIcon>
              <ListItemText>Square</ListItemText>
            </MenuItem>
            <MenuItem onClick={() => handleAspectRatioChange('horizontal')}>
              <ListItemIcon>
                {aspectRatio === 'horizontal' ? (
                  <CheckBoxIcon fontSize="small" color="primary" />
                ) : (
                  <CheckBoxOutlineBlankIcon fontSize="small" />
                )}
              </ListItemIcon>
              <ListItemText>Horizontal</ListItemText>
            </MenuItem>

            <Divider />

            <MenuItem disabled>
              <Typography variant="subtitle2">Thumbnail Scale</Typography>
            </MenuItem>
            <MenuItem onClick={() => handleThumbnailScaleChange('fit')}>
              <ListItemIcon>
                {thumbnailScale === 'fit' ? (
                  <CheckBoxIcon fontSize="small" color="primary" />
                ) : (
                  <CheckBoxOutlineBlankIcon fontSize="small" />
                )}
              </ListItemIcon>
              <ListItemText>Fit</ListItemText>
            </MenuItem>
            <MenuItem onClick={() => handleThumbnailScaleChange('fill')}>
              <ListItemIcon>
                {thumbnailScale === 'fill' ? (
                  <CheckBoxIcon fontSize="small" color="primary" />
                ) : (
                  <CheckBoxOutlineBlankIcon fontSize="small" />
                )}
              </ListItemIcon>
              <ListItemText>Fill</ListItemText>
            </MenuItem>

            <Divider />
          </>
        )}

        <MenuItem onClick={handleShowMetadataChange}>
          <ListItemIcon>
            {showMetadata ? (
              <CheckBoxIcon fontSize="small" color="primary" />
            ) : (
              <CheckBoxOutlineBlankIcon fontSize="small" />
            )}
          </ListItemIcon>
          <ListItemText>Show Metadata</ListItemText>
        </MenuItem>

        <MenuItem onClick={handleGroupByTypeChange}>
          <ListItemIcon>
            {groupByType ? (
              <CheckBoxIcon fontSize="small" color="primary" />
            ) : (
              <CheckBoxOutlineBlankIcon fontSize="small" />
            )}
          </ListItemIcon>
          <ListItemText>Group by Type</ListItemText>
        </MenuItem>
      </Menu>
    </Paper>
  );
};

export default AssetViewControls;
