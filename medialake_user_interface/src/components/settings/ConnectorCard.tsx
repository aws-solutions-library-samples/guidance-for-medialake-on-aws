import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  Box,
  IconButton,
  Chip,
  useTheme,
  Tooltip,
  LinearProgress,
} from '@mui/material';
import {
  Edit as EditIcon,
  Delete as DeleteIcon,
  Storage as StorageIcon,
  CloudQueue as CloudIcon,
  Check as CheckIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import { ConnectorResponse } from '../../api/types/api.types';

interface ConnectorCardProps {
  connector: ConnectorResponse;
  onEdit: (connector: ConnectorResponse) => void;
  onDelete: (id: string) => Promise<void>;
}

const ConnectorCard: React.FC<ConnectorCardProps> = ({ connector, onEdit, onDelete }) => {
  const theme = useTheme();

  const getConnectorTypeIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'amazons3':
        return <StorageIcon aria-hidden="true" />;
      case 'googlecloudstorage':
        return <CloudIcon aria-hidden="true" />;
      default:
        return <StorageIcon aria-hidden="true" />;
    }
  };

  const getConnectorTypeColor = (type: string) => {
    switch (type.toLowerCase()) {
      case 'amazons3':
        return theme.palette.primary.main;
      case 'googlecloudstorage':
        return theme.palette.success.main;
      default:
        return theme.palette.info.main;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'active':
        return theme.palette.success.main;
      case 'warning':
        return theme.palette.warning.main;
      case 'error':
        return theme.palette.error.main;
      default:
        return theme.palette.grey[500];
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case 'active':
        return <CheckIcon fontSize="small" aria-hidden="true" />;
      case 'warning':
        return <WarningIcon fontSize="small" aria-hidden="true" />;
      default:
        return null;
    }
  };

  const handleDelete = async () => {
    if (window.confirm('Are you sure you want to delete this connector?')) {
      await onDelete(connector.id);
    }
  };

  return (
    <Card
      component="article"
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
        transition: 'transform 0.2s, box-shadow 0.2s',
        '&:hover': {
          transform: 'translateY(-2px)',
          boxShadow: theme.shadows[4],
        },
      }}
    >
      <CardContent sx={{ flex: 1, pb: 2 }}>
        {/* Header */}
        <Box
          component="header"
          sx={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            mb: 2
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box
              sx={{
                backgroundColor: `${getConnectorTypeColor(connector.type)}15`,
                borderRadius: '8px',
                p: 1,
                display: 'flex',
                alignItems: 'center',
                color: getConnectorTypeColor(connector.type),
              }}
              aria-hidden="true"
            >
              {getConnectorTypeIcon(connector.type)}
            </Box>
            <Box>
              <Typography variant="h6" component="h2" sx={{ fontWeight: 600 }}>
                {connector.name}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {connector.type === 'amazonS3' ? 'Amazon S3' : 'Google Cloud Storage'}
              </Typography>
            </Box>
          </Box>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Tooltip title="Edit connector">
              <IconButton
                size="small"
                onClick={() => onEdit(connector)}
                sx={{ color: theme.palette.text.secondary }}
                aria-label={`Edit ${connector.name}`}
              >
                <EditIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title="Delete connector">
              <IconButton
                size="small"
                onClick={handleDelete}
                sx={{ color: theme.palette.error.main }}
                aria-label={`Delete ${connector.name}`}
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>

        {/* Stats */}
        <Box component="section" sx={{ mb: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
            <Typography variant="body2" color="text.secondary" component="span">
              Storage Usage
            </Typography>
            <Typography variant="body2" fontWeight={500} component="span">
              {connector.usage?.used || '0'} / {connector.usage?.total || '0'} GB
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={((connector.usage?.used || 0) / (connector.usage?.total || 1)) * 100}
            sx={{
              height: 6,
              borderRadius: 3,
              backgroundColor: theme.palette.grey[200],
              '& .MuiLinearProgress-bar': {
                borderRadius: 3,
                backgroundColor: getConnectorTypeColor(connector.type),
              },
            }}
            aria-label={`Storage usage: ${connector.usage?.used || '0'} of ${connector.usage?.total || '0'} GB`}
          />
        </Box>

        {/* Footer */}
        <Box
          component="footer"
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}
        >
          <Chip
            icon={getStatusIcon(connector.status || 'active')}
            label={connector.status || 'Active'}
            size="small"
            sx={{
              backgroundColor: `${getStatusColor(connector.status || 'active')}15`,
              color: getStatusColor(connector.status || 'active'),
              fontWeight: 500,
            }}
            role="status"
          />
          <Typography variant="caption" color="text.secondary">
            Last synced: {new Date(connector.lastSync || Date.now()).toLocaleDateString()}
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
};

export default ConnectorCard;
