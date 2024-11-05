import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import IntegrationsPage from './IntegrationsPage';
import ConnectorsPage from './ConnectorsPage';
import SystemPage from './SystemPage';
import ProfilePage from './ProfilePage';

const SettingsRouter: React.FC = () => {
    return (
        <Routes>
            <Route path="integrations" element={<IntegrationsPage />} />
            <Route path="connectors" element={<ConnectorsPage />} />
            <Route path="system" element={<SystemPage />} />
            <Route path="profile" element={<ProfilePage />} />
            <Route path="*" element={<Navigate to="profile" replace />} />
        </Routes>
    );
};

export default SettingsRouter;
