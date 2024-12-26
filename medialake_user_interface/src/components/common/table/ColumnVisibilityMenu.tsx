import React from 'react';
import {
    Menu,
    MenuItem,
    Typography,
    FormControlLabel,
    Checkbox,
    useTheme,
} from '@mui/material';
import { Column } from '@tanstack/react-table';

interface ColumnVisibilityMenuProps {
    anchorEl: HTMLElement | null;
    columns: Column<any, unknown>[];
    onClose: () => void;
    excludeIds?: string[];
}

export const ColumnVisibilityMenu: React.FC<ColumnVisibilityMenuProps> = ({
    anchorEl,
    columns,
    onClose,
    excludeIds = ['actions'],
}) => {
    const theme = useTheme();

    return (
        <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={onClose}
            PaperProps={{
                sx: {
                    maxHeight: 300,
                    width: 200,
                    borderRadius: '8px',
                    boxShadow: theme.shadows[3],
                },
            }}
        >
            {columns.map(column => {
                if (excludeIds.includes(column.id)) return null;
                return (
                    <MenuItem
                        key={column.id}
                        sx={{ py: 1 }}
                    >
                        <FormControlLabel
                            control={
                                <Checkbox
                                    checked={column.getIsVisible()}
                                    onChange={column.getToggleVisibilityHandler()}
                                    sx={{ mr: 1 }}
                                />
                            }
                            label={
                                <Typography variant="body2">
                                    {column.columnDef.header as string}
                                </Typography>
                            }
                            sx={{ m: 0 }}
                        />
                    </MenuItem>
                );
            })}
        </Menu>
    );
};
