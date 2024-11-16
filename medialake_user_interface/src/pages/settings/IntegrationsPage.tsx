import React, { useState } from 'react';
import IntegrationsView from '@/features/settings/integrations/components/IntegrationsView';
import IntegrationModal from '@/features/settings/integrations/components/IntegrationModal';
import { Integration } from '@/api/types/api.types';

const IntegrationsPage: React.FC = () => {
    const [openIntegrationModal, setOpenIntegrationModal] = useState(false);
    const [editingIntegration, setEditingIntegration] = useState<Integration | undefined>();
    const [integrations, setIntegrations] = useState<Integration[]>([]);

    const handleAddIntegration = () => {
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

    return (
        <>
            <IntegrationsView
                integrations={integrations}
                onAddIntegration={handleAddIntegration}
                onEditIntegration={(integration) => {
                    setEditingIntegration(integration);
                    setOpenIntegrationModal(true);
                }}
                onDeleteIntegration={(id) => {
                    setIntegrations(integrations.filter(i => i.id !== id));
                }}
                onConfigureIntegration={() => { }}
            />
            <IntegrationModal
                open={openIntegrationModal}
                onClose={() => {
                    setOpenIntegrationModal(false);
                    setEditingIntegration(undefined);
                }}
                onSave={handleSaveIntegration}
                editingIntegration={editingIntegration}
            />
        </>
    );
};

export default IntegrationsPage;
