import React from 'react';
import { Box, Typography } from '@mui/material';
import { ConnectorsList } from '../../components/ConnectorsList';

const ConnectorsPage: React.FC = () => {
    return (
        <Box>
            <Box sx={{ mb: 4 }}>
                <Typography variant="h4" sx={{ fontWeight: 600, mb: 1 }}>
                    Storage Connectors
                </Typography>
                <Typography variant="body1" color="text.secondary">
                    Manage your storage connections and data sources
                </Typography>
            </Box>
            <ConnectorsList />
        </Box>
    );
};

export default ConnectorsPage;
