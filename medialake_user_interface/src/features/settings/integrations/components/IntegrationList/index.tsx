import React from 'react';
import {
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Paper,
    IconButton,
    Chip,
    Box,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import { Integration, IntegrationListProps } from './types';

const IntegrationList: React.FC<IntegrationListProps> = ({
    integrations,
    onEditIntegration,
    onDeleteIntegration,
    activeFilters,
    activeSorting,
    onFilterChange,
    onSortChange,
    onRemoveFilter,
    onRemoveSort,
}) => {
    const getStatusColor = (status: string) => {
        switch (status.toLowerCase()) {
            case 'active':
                return 'success';
            case 'error':
                return 'error';
            default:
                return 'warning';
        }
    };

    return (
        <TableContainer component={Paper}>
            <Table>
                <TableHead>
                    <TableRow>
                        <TableCell>Name</TableCell>
                        <TableCell>Type</TableCell>
                        <TableCell>Status</TableCell>
                        <TableCell>Created</TableCell>
                        <TableCell>Updated</TableCell>
                        <TableCell>Actions</TableCell>
                    </TableRow>
                </TableHead>
                <TableBody>
                    {integrations.map((integration) => (
                        <TableRow key={integration.id}>
                            <TableCell>{integration.name}</TableCell>
                            <TableCell>{integration.type}</TableCell>
                            <TableCell>
                                <Chip
                                    label={integration.status}
                                    color={getStatusColor(integration.status) as any}
                                    size="small"
                                />
                            </TableCell>
                            <TableCell>{new Date(integration.createdAt).toLocaleDateString()}</TableCell>
                            <TableCell>{new Date(integration.updatedAt).toLocaleDateString()}</TableCell>
                            <TableCell>
                                <Box sx={{ display: 'flex', gap: 1 }}>
                                    <IconButton
                                        size="small"
                                        onClick={() => onEditIntegration(integration.id, integration)}
                                    >
                                        <EditIcon />
                                    </IconButton>
                                    <IconButton
                                        size="small"
                                        onClick={() => onDeleteIntegration(integration.id)}
                                    >
                                        <DeleteIcon />
                                    </IconButton>
                                </Box>
                            </TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </TableContainer>
    );
};

export default React.memo(IntegrationList);
