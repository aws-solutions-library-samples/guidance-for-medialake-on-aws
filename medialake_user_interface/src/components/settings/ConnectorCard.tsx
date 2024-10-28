import React from 'react';
import {
    Box,
    Typography,
    Card,
    CardContent,
    IconButton,
} from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import { ConnectorResponse } from '../../api/types/api.types';

interface ConnectorCardProps {
    connector: ConnectorResponse;
    onEdit: (connector: ConnectorResponse) => void;
    onDelete: (id: string) => void;
}

export const ConnectorCard: React.FC<ConnectorCardProps> = ({
    connector,
    onEdit,
    onDelete,
}) => {
    return (
        <Card>
            <CardContent>
                <Typography variant="h6">{connector.name}</Typography>
                <Typography>Type: {connector.type}</Typography>
                <Typography>
                    Created: {new Date(connector.created_at).toLocaleDateString()}
                </Typography>
                <Box sx={{ mt: 2 }}>
                    <IconButton aria-label="edit" onClick={() => onEdit(connector)}>
                        <EditIcon />
                    </IconButton>
                    <IconButton
                        aria-label="delete"
                        onClick={() => onDelete(connector.id)}
                    >
                        <DeleteIcon />
                    </IconButton>
                </Box>
            </CardContent>
        </Card>
    );
};

export default ConnectorCard;
