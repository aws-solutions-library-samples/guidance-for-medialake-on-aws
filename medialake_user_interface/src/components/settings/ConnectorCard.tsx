import React from 'react';
import { Card, CardContent, Typography, Box, Button } from '@mui/material';
import { format } from 'date-fns';
import { ConnectorResponse } from '../../api/types/api.types';

interface ConnectorCardProps {
  connector: ConnectorResponse;
  onEdit: (connector: ConnectorResponse) => void;
  onDelete: (id: string) => Promise<void>;
}

const ConnectorCard: React.FC<ConnectorCardProps> = ({ connector, onEdit, onDelete }) => {
  const formatDate = (dateString: string) => {
    try {
      return format(new Date(dateString), 'MMM dd, yyyy HH:mm');
    } catch (error) {
      return dateString;
    }
  };

  return (
    <Card sx={{ minWidth: 275, mb: 2 }}>
      <CardContent>
        <Typography variant="h6" component="div" gutterBottom>
          {connector.name}
        </Typography>
        <Box sx={{ mt: 1 }}>
          <Typography color="text.secondary" gutterBottom>
            Bucket: {connector.storageIdentifier}
          </Typography>
          <Typography color="text.secondary" gutterBottom>
            Type: {connector.type}
          </Typography>
          <Typography color="text.secondary" gutterBottom>
            Created: {formatDate(connector.createdAt)}
          </Typography>
          <Typography color="text.secondary">
            Updated: {formatDate(connector.updatedAt)}
          </Typography>
        </Box>
        <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
          <Button variant="outlined" onClick={() => onEdit(connector)}>
            Edit
          </Button>
          <Button variant="outlined" color="error" onClick={() => onDelete(connector.id)}>
            Delete
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
};

export default ConnectorCard;
