import { useMemo } from 'react';
import { createColumnHelper } from '@tanstack/react-table';
import { Box, Tooltip, IconButton, Typography, Chip } from '@mui/material';
import {
    Edit as EditIcon,
    Delete as DeleteIcon,
    PlayArrow as PlayIcon,
    Stop as StopIcon
} from '@mui/icons-material';
import { TableCellContent } from '@/components/common/table';
import { format } from 'date-fns';
import { Pipeline } from '../types/pipelines.types';

interface UsePipelineColumnsProps {
    onEdit: (id: string) => void;
    onDelete: (id: string, name: string) => void;
    onStart: (id: string) => void;
    onStop: (id: string) => void;
}

const columnHelper = createColumnHelper<Pipeline>();

export const usePipelineColumns = ({
    onEdit,
    onDelete,
    onStart,
    onStop
}: UsePipelineColumnsProps) => {
    return useMemo(
        () => [
            columnHelper.accessor('name', {
                header: 'Name',
                size: 200,
                enableSorting: true,
                cell: ({ getValue }) => (
                    <TableCellContent variant="primary">
                        {getValue()}
                    </TableCellContent>
                ),
            }),
            columnHelper.accessor('type', {
                header: 'Type',
                size: 150,
                enableSorting: true,
                cell: info => (
                    <TableCellContent variant="secondary">
                        <Chip
                            label={info.getValue()}
                            size="small"
                            color={info.getValue() === 'Ingest Triggered' ? 'primary' : 'default'}
                        />
                    </TableCellContent>
                ),
            }),
            columnHelper.accessor('system', {
                header: 'System',
                size: 100,
                enableSorting: true,
                cell: info => (
                    <TableCellContent variant="secondary">
                        <Chip
                            label={info.getValue() ? 'Yes' : 'No'}
                            size="small"
                            color={info.getValue() ? 'success' : 'default'}
                        />
                    </TableCellContent>
                ),
            }),
            columnHelper.accessor('deploymentStatus', {
                header: 'Status',
                size: 120,
                enableSorting: true,
                cell: info => {
                    const status = info.getValue();
                    let color: 'text.secondary' | 'success.main' | 'info.main' | 'error.main' = 'text.secondary';
                    
                    if (status === 'DEPLOYED') {
                        color = 'success.main';
                    } else if (status === 'CREATING') {
                        color = 'info.main';
                    } else if (status === 'FAILED') {
                        color = 'error.main';
                    }
                    
                    return (
                        <TableCellContent variant="secondary">
                            <Typography
                                variant="body2"
                                sx={{
                                    color: color,
                                    fontWeight: 'medium'
                                }}
                            >
                                {status || 'N/A'}
                            </Typography>
                        </TableCellContent>
                    );
                },
            }),
            columnHelper.accessor('createdAt', {
                header: 'Created',
                size: 180,
                enableSorting: true,
                cell: ({ getValue }) => {
                    const dateValue = getValue();
                    return (
                        <Tooltip title={format(new Date(dateValue), 'MMM dd, yyyy HH:mm')} placement="top">
                            <Box>
                                <TableCellContent variant="secondary">
                                    {format(new Date(dateValue), 'MMM dd, yyyy')}
                                </TableCellContent>
                            </Box>
                        </Tooltip>
                    );
                },
            }),
            columnHelper.accessor('updatedAt', {
                header: 'Updated',
                size: 180,
                enableSorting: true,
                cell: ({ getValue }) => {
                    const dateValue = getValue();
                    return (
                        <Tooltip title={format(new Date(dateValue), 'MMM dd, yyyy HH:mm')} placement="top">
                            <Box>
                                <TableCellContent variant="secondary">
                                    {format(new Date(dateValue), 'MMM dd, yyyy')}
                                </TableCellContent>
                            </Box>
                        </Tooltip>
                    );
                },
            }),
            columnHelper.display({
                id: 'actions',
                header: 'Actions',
                size: 200,
                cell: info => (
                    <Box sx={{ display: 'flex', gap: 1 }} className="action-buttons">
                        <Tooltip title={
                            info.row.original.deploymentStatus &&
                            !['DEPLOYED', 'FAILED'].includes(info.row.original.deploymentStatus)
                                ? "Cannot edit pipeline while it's being created"
                                : "Edit Pipeline"
                        }>
                            <span>
                                <IconButton
                                    size="small"
                                    onClick={() => onEdit(info.row.original.id)}
                                    disabled={
                                        info.row.original.deploymentStatus &&
                                        !['DEPLOYED', 'FAILED'].includes(info.row.original.deploymentStatus)
                                    }
                                >
                                    <EditIcon fontSize="small" />
                                </IconButton>
                            </span>
                        </Tooltip>
                        <Tooltip title={
                            info.row.original.deploymentStatus &&
                            !['DEPLOYED', 'FAILED'].includes(info.row.original.deploymentStatus)
                                ? "Cannot delete pipeline while it's being created"
                                : "Delete Pipeline"
                        }>
                            <span>
                                <IconButton
                                    size="small"
                                    onClick={() => onDelete(info.row.original.id, info.row.original.name)}
                                    disabled={
                                        info.row.original.system ||
                                        (info.row.original.deploymentStatus &&
                                        !['DEPLOYED', 'FAILED'].includes(info.row.original.deploymentStatus))
                                    }
                                >
                                <DeleteIcon fontSize="small" />
                            </IconButton>
                            </span>
                        </Tooltip>
                        <Tooltip title="Start Pipeline">
                            <IconButton
                                size="small"
                                onClick={() => onStart(info.row.original.id)}
                                disabled={true}
                            >
                                <PlayIcon fontSize="small" />
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Stop Pipeline">
                            <IconButton
                                size="small"
                                onClick={() => onStop(info.row.original.id)}
                                disabled={true}
                            >
                                <StopIcon fontSize="small" />
                            </IconButton>
                        </Tooltip>
                    </Box>
                ),
            }),
        ],
        [onEdit, onDelete, onStart, onStop]
    );
};

export const defaultColumnVisibility = {
    name: true,
    type: true,
    system: true,
    deploymentStatus: true,
    createdAt: true,
    updatedAt: true,
    actions: true,
};