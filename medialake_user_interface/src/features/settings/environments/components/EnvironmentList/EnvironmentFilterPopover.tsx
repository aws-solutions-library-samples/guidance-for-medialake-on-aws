import React from 'react';
import {
    Box,
    TextField,
    Popover,
    Select,
    MenuItem,
    Button,
    useTheme,
    Typography,
    Stack,
} from '@mui/material';
import { Column } from '@tanstack/react-table';
import { Environment } from '@/types/environment';
import { useTranslation } from 'react-i18next';

interface EnvironmentFilterPopoverProps {
    anchorEl: HTMLElement | null;
    column: Column<Environment, unknown> | null;
    onClose: () => void;
    environments: Environment[];
}

export const EnvironmentFilterPopover: React.FC<EnvironmentFilterPopoverProps> = ({
    anchorEl,
    column,
    onClose,
    environments,
}) => {
    const { t } = useTranslation();
    const theme = useTheme();

    const formatDateOnly = (dateString: string) => {
        const date = new Date(dateString);
        return date.toLocaleDateString();
    };

    const getUniqueColumnValues = (columnId: string) => {
        const values = new Set<string>();
        environments.forEach(env => {
            let value: any;
            if (columnId === 'team' || columnId === 'cost-center') {
                value = env.tags?.[columnId];
            } else {
                value = env[columnId as keyof Environment];
            }

            if (value != null) {
                if (columnId === 'created_at' || columnId === 'updated_at') {
                    values.add(formatDateOnly(String(value)));
                } else {
                    values.add(String(value));
                }
            }
        });
        return Array.from(values).sort();
    };

    if (!column) return null;

    const uniqueValues = getUniqueColumnValues(column.id);
    const currentValue = column.getFilterValue() as string;

    const handleTextFilterChange = (value: string) => {
        if (value) {
            column.setFilterValue(value);
        } else {
            column.setFilterValue('');
        }
    };

    const handleSelectFilterChange = (value: string) => {
        if (value) {
            if (column.id === 'created_at' || column.id === 'updated_at') {
                column.setFilterValue((prev: any) => ({
                    value,
                    filterDate: true
                }));
            } else {
                column.setFilterValue(value);
            }
        } else {
            column.setFilterValue('');
        }
    };

    const handleClearFilter = () => {
        column.setFilterValue('');
    };

    return (
        <Popover
            open={Boolean(anchorEl)}
            anchorEl={anchorEl}
            onClose={onClose}
            anchorOrigin={{
                vertical: 'bottom',
                horizontal: 'left',
            }}
            transformOrigin={{
                vertical: 'top',
                horizontal: 'left',
            }}
            PaperProps={{
                sx: {
                    p: 2,
                    width: 300,
                    borderRadius: '8px',
                },
            }}
        >
            <Stack spacing={2}>
                <Box>
                    <Typography variant="caption" color="textSecondary" sx={{ mb: 1, display: 'block' }}>
                        {t('common.textFilter')}
                    </Typography>
                    <TextField
                        fullWidth
                        size="small"
                        placeholder={`${t('common.filter')} ${column.columnDef.header as string}`}
                        value={currentValue ?? ''}
                        onChange={e => handleTextFilterChange(e.target.value)}
                        sx={{
                            '& .MuiOutlinedInput-root': {
                                borderRadius: '8px',
                            },
                        }}
                    />
                </Box>

                <Box>
                    <Typography variant="caption" color="textSecondary" sx={{ mb: 1, display: 'block' }}>
                        {t('common.selectFilter')}
                    </Typography>
                    <Select
                        fullWidth
                        size="small"
                        value={currentValue ?? ''}
                        onChange={e => handleSelectFilterChange(e.target.value)}
                        displayEmpty
                        sx={{
                            borderRadius: '8px',
                        }}
                    >
                        <MenuItem value="">
                            <em>{t('common.all')}</em>
                        </MenuItem>
                        {uniqueValues.map((value) => (
                            <MenuItem key={value} value={value}>
                                {column.id === 'status'
                                    ? value === 'active' ? t('settings.environments.status.active') : t('settings.environments.status.disabled')
                                    : value}
                            </MenuItem>
                        ))}
                    </Select>
                </Box>

                {currentValue && (
                    <Button
                        size="small"
                        onClick={handleClearFilter}
                        sx={{ alignSelf: 'flex-start' }}
                    >
                        {t('common.clearFilter')}
                    </Button>
                )}
            </Stack>
        </Popover>
    );
};
