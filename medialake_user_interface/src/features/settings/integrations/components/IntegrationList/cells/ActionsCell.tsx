import React from 'react';
import {
    Box,
    IconButton,
    Tooltip,
    useTheme,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import { Row } from '@tanstack/react-table';
import { Integration } from '../types';

interface ActionsCellProps {
    row: Row<Integration>;
    onEdit: (integration: Integration) => void;
    onDelete: (id: string) => void;
}

const ActionsCell = React.memo(({ row, onEdit, onDelete }: ActionsCellProps) => {
    const theme = useTheme();
    return (
        <Box sx={{ display: 'flex', gap: 1 }}>
            <Tooltip title="Edit Integration">
                <IconButton
                    onClick={() => onEdit(row.original)}
                    size="small"
                    sx={{ color: theme.palette.primary.main }}
                >
                    <EditIcon />
                </IconButton>
            </Tooltip>
            <Tooltip title="Delete Integration">
                <IconButton
                    onClick={() => onDelete(row.original.id)}
                    size="small"
                    sx={{ color: theme.palette.error.main }}
                >
                    <DeleteIcon />
                </IconButton>
            </Tooltip>
        </Box>
    );
});

ActionsCell.displayName = 'ActionsCell';

export default ActionsCell;
