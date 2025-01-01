import React from 'react';
import { IconButton, Tooltip } from '@mui/material';
import DensitySmallIcon from '@mui/icons-material/DensitySmall';
import DensityLargeIcon from '@mui/icons-material/DensityLarge';
import { useTableDensity } from '../../../contexts/TableDensityContext';
import { useTranslation } from 'react-i18next';

export const TableDensityToggle: React.FC = () => {
    const { t } = useTranslation();
    const { mode, toggleMode } = useTableDensity();

    return (
        <Tooltip title={t('common.tableDensity', 'Table Density')}>
            <IconButton
                onClick={toggleMode}
                size="small"
                aria-label={t('common.tableDensity', 'Table Density')}
            >
                {mode === 'compact' ? <DensitySmallIcon /> : <DensityLargeIcon />}
            </IconButton>
        </Tooltip>
    );
};
