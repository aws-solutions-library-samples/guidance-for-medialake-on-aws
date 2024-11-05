import React from 'react';
import { Box } from '@mui/material';
import { Routes, Route, Navigate } from 'react-router-dom';
import IntegrationsPage from './pages/settings/IntegrationsPage';
import ConnectorsPage from './pages/settings/ConnectorsPage';
import SystemPage from './pages/settings/SystemPage';
import ProfilePage from './pages/settings/ProfilePage';

const SettingsComponent: React.FC = () => {
    return (
        <Box sx={{ maxWidth: 1200, margin: '0 auto' }}>
            <Routes>
                <Route path="profile" element={<ProfilePage />} />
                <Route path="integrations" element={<IntegrationsPage />} />
                <Route path="connectors" element={<ConnectorsPage />} />
                <Route path="system" element={<SystemPage />} />
                <Route path="/" element={<Navigate to="profile" replace />} />
                <Route path="*" element={<Navigate to="profile" replace />} />
            </Routes>
        </Box>
    );
};

export default SettingsComponent;
