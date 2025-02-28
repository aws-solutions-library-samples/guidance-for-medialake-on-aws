import React from 'react';
import {
    Box,
    Typography,
    Button,
    ToggleButtonGroup,
    ToggleButton,
    Menu,
    MenuItem,
    FormGroup,
    FormControlLabel,
    Checkbox,
    Switch,
    Radio,
    ListItemIcon,
    ListItemText,
} from '@mui/material';
import ViewModuleIcon from '@mui/icons-material/ViewModule';
import ViewListIcon from '@mui/icons-material/ViewList';
import ViewColumnIcon from '@mui/icons-material/ViewColumn';
import SortIcon from '@mui/icons-material/Sort';
import TuneIcon from '@mui/icons-material/Tune';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import CropPortraitIcon from '@mui/icons-material/CropPortrait';
import CropSquareIcon from '@mui/icons-material/CropSquare';
import CropLandscapeIcon from '@mui/icons-material/CropLandscape';
import PhotoSizeSelectSmallIcon from '@mui/icons-material/PhotoSizeSelectSmall';
import PhotoSizeSelectLargeIcon from '@mui/icons-material/PhotoSizeSelectLarge';
import FitScreenIcon from '@mui/icons-material/FitScreen';
import FullscreenIcon from '@mui/icons-material/Fullscreen';
import InfoIcon from '@mui/icons-material/Info';
import { type SortingState } from '@tanstack/react-table';
import { type AssetField, type SortOption, type CardSize, type AspectRatio, type AssetViewControlsProps as BaseAssetViewControlsProps } from '../../types/shared/assetComponents';

interface AssetViewControlsProps extends BaseAssetViewControlsProps {
    groupByType: boolean;
    onGroupByTypeChange: (checked: boolean) => void;
    cardSize: CardSize;
    onCardSizeChange: (size: CardSize) => void;
    aspectRatio: AspectRatio;
    onAspectRatioChange: (ratio: AspectRatio) => void;
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
    onShowMetadataChange,
}) => {
    const [sortAnchor, setSortAnchor] = React.useState<null | HTMLElement>(null);
    const [fieldsAnchor, setFieldsAnchor] = React.useState<null | HTMLElement>(null);
    const [appearanceAnchor, setAppearanceAnchor] = React.useState<null | HTMLElement>(null);

    const handleSortClose = () => setSortAnchor(null);
    const handleFieldsClose = () => setFieldsAnchor(null);
    const handleAppearanceClose = () => setAppearanceAnchor(null);

    return (
        <Box sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 3
        }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Typography
                    variant="h5"
                    component="h2"
                    sx={{
                        fontWeight: 600,
                        color: 'text.primary',
                    }}
                >
                    {title}
                </Typography>
                <ToggleButtonGroup
                    value={viewMode}
                    exclusive
                    onChange={onViewModeChange}
                    size="small"
                >
                    <ToggleButton value="card">
                        <ViewModuleIcon />
                    </ToggleButton>
                    <ToggleButton value="table">
                        <ViewListIcon />
                    </ToggleButton>
                </ToggleButtonGroup>
            </Box>

            <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                {/* Sort Button */}
                <Button
                    size="small"
                    startIcon={<SortIcon />}
                    endIcon={<KeyboardArrowDownIcon />}
                    onClick={(e) => setSortAnchor(e.currentTarget)}
                    sx={{
                        bgcolor: Boolean(sortAnchor) ? 'action.selected' : 'transparent',
                        textTransform: 'none',
                    }}
                >
                    Sort
                </Button>

                {/* Show Fields Button */}
                <Button
                    size="small"
                    startIcon={<ViewColumnIcon />}
                    endIcon={<KeyboardArrowDownIcon />}
                    onClick={(e) => setFieldsAnchor(e.currentTarget)}
                    sx={{
                        bgcolor: Boolean(fieldsAnchor) ? 'action.selected' : 'transparent',
                        textTransform: 'none',
                    }}
                >
                    Fields
                </Button>

                {/* Appearance Button */}
                <Button
                    size="small"
                    startIcon={<TuneIcon />}
                    endIcon={<KeyboardArrowDownIcon />}
                    onClick={(e) => setAppearanceAnchor(e.currentTarget)}
                    sx={{
                        bgcolor: Boolean(appearanceAnchor) ? 'action.selected' : 'transparent',
                        textTransform: 'none',
                    }}
                >
                    Appearance
                </Button>
            </Box>

            {/* Sort Menu */}
            <Menu
                open={Boolean(sortAnchor)}
                anchorEl={sortAnchor}
                onClose={handleSortClose}
                anchorOrigin={{
                    vertical: 'bottom',
                    horizontal: 'right',
                }}
                transformOrigin={{
                    vertical: 'top',
                    horizontal: 'right',
                }}
            >
                <Box sx={{ p: 2, minWidth: 200 }}>
                    <Typography variant="subtitle2" sx={{ mb: 1 }}>
                        Sort By
                    </Typography>
                    {sortOptions.map((option) => (
                        <MenuItem
                            key={option.id}
                            onClick={() => {
                                onSortChange(option.id);
                                handleSortClose();
                            }}
                            sx={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                py: 1,
                            }}
                        >
                            <Typography variant="body2">
                                {option.label}
                            </Typography>
                            {sorting[0]?.id === option.id && (
                                <Typography variant="caption" color="primary">
                                    {sorting[0]?.desc ? '↓' : '↑'}
                                </Typography>
                            )}
                        </MenuItem>
                    ))}
                </Box>
            </Menu>

            {/* Show Fields Menu */}
            <Menu
                open={Boolean(fieldsAnchor)}
                anchorEl={fieldsAnchor}
                onClose={handleFieldsClose}
                anchorOrigin={{
                    vertical: 'bottom',
                    horizontal: 'right',
                }}
                transformOrigin={{
                    vertical: 'top',
                    horizontal: 'right',
                }}
            >
                <Box sx={{ p: 2, minWidth: 200 }}>
                    <Typography variant="subtitle2" sx={{ mb: 1 }}>
                        {viewMode === 'card' ? 'Show Fields' : 'Show Columns'}
                    </Typography>
                    <FormGroup>
                        {fields.map((field) => (
                            <FormControlLabel
                                key={field.id}
                                control={
                                    <Checkbox
                                        checked={field.visible}
                                        onChange={() => onFieldToggle(field.id)}
                                        size="small"
                                    />
                                }
                                label={field.label}
                                sx={{
                                    '& .MuiFormControlLabel-label': {
                                        fontSize: '0.875rem'
                                    }
                                }}
                            />
                        ))}
                    </FormGroup>
                </Box>
            </Menu>

            {/* Appearance Menu */}
            <Menu
                open={Boolean(appearanceAnchor)}
                anchorEl={appearanceAnchor}
                onClose={handleAppearanceClose}
                anchorOrigin={{
                    vertical: 'bottom',
                    horizontal: 'right',
                }}
                transformOrigin={{
                    vertical: 'top',
                    horizontal: 'right',
                }}
            >
                <Box sx={{ p: 2, minWidth: 300 }}>
                    <Typography variant="subtitle2" sx={{ mb: 2 }}>
                        Appearance
                    </Typography>
                    
                    {viewMode === 'card' && (
                        <>
                            <Box sx={{ mb: 2 }}>
                                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                                    Card Size
                                </Typography>
                                <Box sx={{ display: 'flex', gap: 1 }}>
                                    <ToggleButton
                                        value="small"
                                        selected={cardSize === 'small'}
                                        onChange={() => onCardSizeChange('small')}
                                        size="small"
                                    >
                                        <PhotoSizeSelectSmallIcon />
                                    </ToggleButton>
                                    <ToggleButton
                                        value="medium"
                                        selected={cardSize === 'medium'}
                                        onChange={() => onCardSizeChange('medium')}
                                        size="small"
                                    >
                                        <ViewModuleIcon />
                                    </ToggleButton>
                                    <ToggleButton
                                        value="large"
                                        selected={cardSize === 'large'}
                                        onChange={() => onCardSizeChange('large')}
                                        size="small"
                                    >
                                        <PhotoSizeSelectLargeIcon />
                                    </ToggleButton>
                                </Box>
                            </Box>

                            <Box sx={{ mb: 2 }}>
                                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                                    Aspect Ratio
                                </Typography>
                                <Box sx={{ display: 'flex', gap: 1 }}>
                                    <ToggleButton
                                        value="vertical"
                                        selected={aspectRatio === 'vertical'}
                                        onChange={() => onAspectRatioChange('vertical')}
                                        size="small"
                                    >
                                        <CropPortraitIcon />
                                    </ToggleButton>
                                    <ToggleButton
                                        value="square"
                                        selected={aspectRatio === 'square'}
                                        onChange={() => onAspectRatioChange('square')}
                                        size="small"
                                    >
                                        <CropSquareIcon />
                                    </ToggleButton>
                                    <ToggleButton
                                        value="horizontal"
                                        selected={aspectRatio === 'horizontal'}
                                        onChange={() => onAspectRatioChange('horizontal')}
                                        size="small"
                                    >
                                        <CropLandscapeIcon />
                                    </ToggleButton>
                                </Box>
                            </Box>

                            <Box sx={{ mb: 2 }}>
                                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                                    Thumbnail Scale
                                </Typography>
                                <Box sx={{ display: 'flex', gap: 1 }}>
                                    <ToggleButton
                                        value="fit"
                                        selected={thumbnailScale === 'fit'}
                                        onChange={() => onThumbnailScaleChange('fit')}
                                        size="small"
                                    >
                                        <FitScreenIcon />
                                    </ToggleButton>
                                    <ToggleButton
                                        value="fill"
                                        selected={thumbnailScale === 'fill'}
                                        onChange={() => onThumbnailScaleChange('fill')}
                                        size="small"
                                    >
                                        <FullscreenIcon />
                                    </ToggleButton>
                                </Box>
                            </Box>
                        </>
                    )}

                    <Box sx={{ display: 'flex', gap: 2 }}>
                        <FormControlLabel
                            control={
                                <Switch
                                    checked={groupByType}
                                    onChange={(e) => onGroupByTypeChange(e.target.checked)}
                                    size="small"
                                />
                            }
                            label="Group by Type"
                            sx={{
                                '& .MuiFormControlLabel-label': {
                                    fontSize: '0.875rem'
                                }
                            }}
                        />
                        {viewMode === 'card' && (
                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={showMetadata}
                                        onChange={(e) => onShowMetadataChange(e.target.checked)}
                                        size="small"
                                    />
                                }
                                label="Metadata"
                                sx={{
                                    '& .MuiFormControlLabel-label': {
                                        fontSize: '0.875rem'
                                    }
                                }}
                            />
                        )}
                    </Box>
                </Box>
            </Menu>
        </Box>
    );
};

export default AssetViewControls;
