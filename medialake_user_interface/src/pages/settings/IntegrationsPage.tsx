import React, { useState } from 'react';
import { Box } from '@mui/material';
import IntegrationsView from '../../components/settings/IntegrationsView';
import IntegrationModal from '../../components/settings/IntegrationModal';
import { Integration } from '../../api/types/api.types';

const IntegrationsPage: React.FC = () => {
    const [openIntegrationModal, setOpenIntegrationModal] = useState(false);
    const [editingIntegration, setEditingIntegration] = useState<Integration | undefined>();
    const [integrations, setIntegrations] = useState<Integration[]>([]);

    const handleAddIntegration = () => {
        console.log('Opening integration modal from IntegrationsPage'); // Debug log
        setEditingIntegration(undefined);
        setOpenIntegrationModal(true);
    };

    const handleSaveIntegration = (integration: Integration) => {
        if (editingIntegration) {
            setIntegrations(integrations.map(i =>
                i.id === integration.id ? integration : i
            ));
        } else {
            setIntegrations([...integrations, integration]);
        }
        setOpenIntegrationModal(false);
        setEditingIntegration(undefined);
    };

    const handleDeleteIntegration = (id: string) => {
        setIntegrations(integrations.filter(i => i.id !== id));
    };

    return (
        <Box>
            <IntegrationsView
                integrations={integrations}
                onAddIntegration={handleAddIntegration}
                onEditIntegration={(integration) => {
                    setEditingIntegration(integration);
                    setOpenIntegrationModal(true);
                }}
                onDeleteIntegration={handleDeleteIntegration}
                onConfigureIntegration={() => { }}
            />

            <IntegrationModal
                open={openIntegrationModal}
                onClose={() => {
                    console.log('Closing integration modal'); // Debug log
                    setOpenIntegrationModal(false);
                    setEditingIntegration(undefined);
                }}
                onSave={handleSaveIntegration}
                editingIntegration={editingIntegration}
            />
        </Box>
    );
};

export default IntegrationsPage;
