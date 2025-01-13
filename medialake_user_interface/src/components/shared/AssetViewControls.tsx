import React from 'react';
import { Box, Typography, IconButton, ToggleButtonGroup, ToggleButton, Popover, MenuItem, FormGroup, FormControlLabel, Checkbox } from '@mui/material';
import ViewModuleIcon from '@mui/icons-material/ViewModule';
import ViewListIcon from '@mui/icons-material/ViewList';
import ViewColumnIcon from '@mui/icons-material/ViewColumn';
import SortIcon from '@mui/icons-material/Sort';
import { type SortingState } from '@tanstack/react-table';

export interface AssetField {
    id: string;
    label: string;
    visible: boolean;
}

export interface SortOption {
    id: string;
    label: string;
}

interface AssetViewControlsProps {
    viewMode: 'card' | 'table';
    onViewModeChange: (event: React.MouseEvent<HTMLElement>, newMode: 'card' | 'table' | null) => void;
    title: string;
    sorting: SortingState;
    sortOptions: SortOption[];
    onSortChange: (columnId: string) => void;
    fields: AssetField[];
    onFieldToggle: (fieldId: string) => void;
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
}) => {
    const [sortAnchor, setSortAnchor] = React.useState<null | HTMLElement>(null);
    const [fieldsAnchor, setFieldsAnchor] = React.useState<null | HTMLElement>(null);

    const handleSortClose = () => setSortAnchor(null);
    const handleFieldsClose = () => setFieldsAnchor(null);

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
            <Box sx={{ display: 'flex', gap: 1 }}>
                <IconButton
                    size="small"
                    onClick={(e) => setSortAnchor(e.currentTarget)}
                    sx={{
                        bgcolor: Boolean(sortAnchor) ? 'action.selected' : 'transparent',
                    }}
                >
                    <SortIcon />
                </IconButton>
                <IconButton
                    size="small"
                    onClick={(e) => setFieldsAnchor(e.currentTarget)}
                    sx={{
                        bgcolor: Boolean(fieldsAnchor) ? 'action.selected' : 'transparent',
                    }}
                >
                    <ViewColumnIcon />
                </IconButton>
            </Box>

            <Popover
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
            </Popover>

            <Popover
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
                onClick={(e) => e.stopPropagation()}
                slotProps={{
                    paper: {
                        onClick: (e) => e.stopPropagation(),
                        sx: { p: 2, minWidth: 200 }
                    },
                }}
            >
                <Box>
                    <Typography variant="subtitle2" sx={{ mb: 1 }}>
                        {viewMode === 'card' ? 'Show Fields' : 'Show Columns'}
                    </Typography>
                    <FormGroup onClick={(e) => e.stopPropagation()}>
                        {fields.map((field) => (
                            <FormControlLabel
                                key={field.id}
                                control={
                                    <Checkbox
                                        checked={field.visible}
                                        onChange={(e) => {
                                            e.stopPropagation();
                                            onFieldToggle(field.id);
                                        }}
                                        size="small"
                                        onClick={(e) => e.stopPropagation()}
                                    />
                                }
                                label={field.label}
                                onClick={(e) => e.stopPropagation()}
                                sx={{
                                    '& .MuiFormControlLabel-label': {
                                        fontSize: '0.875rem'
                                    }
                                }}
                            />
                        ))}
                    </FormGroup>
                </Box>
            </Popover>
        </Box>
    );
};

export default AssetViewControls;
