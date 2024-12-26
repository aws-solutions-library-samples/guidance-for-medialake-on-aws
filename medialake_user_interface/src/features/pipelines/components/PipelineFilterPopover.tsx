import React from 'react';
import {
    Popover,
    TextField,
    useTheme,
} from '@mui/material';
import { Column } from '@tanstack/react-table';
import { Pipeline } from '@/api/types/pipeline.types';
import { useTranslation } from 'react-i18next';

interface PipelineFilterPopoverProps {
    anchorEl: HTMLElement | null;
    column: Column<Pipeline> | null;
    onClose: () => void;
}

export const PipelineFilterPopover: React.FC<PipelineFilterPopoverProps> = ({
    anchorEl,
    column,
    onClose,
}) => {
    const theme = useTheme();
    const { t } = useTranslation();

    if (!column) return null;

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
            <TextField
                autoFocus
                fullWidth
                size="small"
                placeholder={t('common.filterColumn', { column: column.columnDef.header })}
                value={(column.getFilterValue() as string) ?? ''}
                onChange={e => column.setFilterValue(e.target.value)}
                sx={{
                    '& .MuiOutlinedInput-root': {
                        borderRadius: '8px',
                    },
                }}
            />
        </Popover>
    );
};
