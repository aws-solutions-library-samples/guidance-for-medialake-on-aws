import React from 'react';
import { Box, Typography } from '@mui/material';
import IntegrationsView from '../../components/settings/IntegrationsView';

const IntegrationsPage: React.FC = () => {
    const [integrations, setIntegrations] = React.useState([]);

    const handleAddIntegration = () => {
        // Implementation
    };

    const handleEditIntegration = () => {
        // Implementation
    };

    const handleDeleteIntegration = () => {
        // Implementation
    };

    const handleConfigureIntegration = () => {
        // Implementation
    };

    return (
        <Box>
            <Box sx={{ mb: 4 }}>
                <Typography variant="h4" sx={{ fontWeight: 600, mb: 1 }}>
                    Integrations
                </Typography>
                <Typography variant="body1" color="text.secondary">
                    Manage your third-party integrations and API connections
                </Typography>
            </Box>
            <IntegrationsView
                integrations={integrations}
                onAddIntegration={handleAddIntegration}
                onEditIntegration={handleEditIntegration}
                onDeleteIntegration={handleDeleteIntegration}
                onConfigureIntegration={handleConfigureIntegration}
            />
        </Box>
    );
};

export default IntegrationsPage;
