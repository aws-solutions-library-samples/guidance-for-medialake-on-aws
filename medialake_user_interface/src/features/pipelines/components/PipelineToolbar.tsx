import React from 'react';
import {
    Box,
    Typography,
    IconButton,
    useTheme,
    alpha,
} from '@mui/material';
import {
    ViewColumn as ViewColumnIcon,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import { SearchField } from '../../../components/common/SearchField';
import { TableDensityToggle } from '../../../components/common/table/TableDensityToggle';

interface PipelineToolbarProps {
    globalFilter: string;
    onGlobalFilterChange: (value: string) => void;
    onColumnMenuOpen: (event: React.MouseEvent<HTMLElement>) => void;
}

export const PipelineToolbar: React.FC<PipelineToolbarProps> = ({
    globalFilter,
    onGlobalFilterChange,
    onColumnMenuOpen,
}) => {
    const { t } = useTranslation();
    const theme = useTheme();

    return (
        <Box sx={{ mb: 4 }}>

            <Box sx={{
                display: 'flex',
                gap: 2,
                mb: 2,
                alignItems: 'center',
                height: '40px',
            }}>
                <SearchField
                    value={globalFilter ?? ''}
                    onChange={onGlobalFilterChange}
                    placeholder={t('pipelines.search')}
                />
                <Box sx={{ flex: 1 }} />
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                    <TableDensityToggle />
                    <IconButton
                        onClick={onColumnMenuOpen}
                        sx={{
                            width: '40px',
                            height: '40px',
                            borderRadius: '8px',
                            border: `1px solid ${alpha(theme.palette.divider, 0.2)}`,
                            color: theme.palette.text.secondary,
                            '&:hover': {
                                backgroundColor: alpha(theme.palette.primary.main, 0.1),
                            },
                        }}
                    >
                        <ViewColumnIcon />
                    </IconButton>
                </Box>
            </Box>
        </Box>
    );
};
