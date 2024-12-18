import React from 'react';
import { Box } from '@mui/material';
import { Routes, Route, Navigate } from 'react-router-dom';
import ConnectorsPage from '../../pages/settings/ConnectorsPage';
import ProfilePage from '../../pages/settings/ProfilePage';
import UserManagement from '../../pages/settings/UserManagement';
import RoleManagement from '../../pages/settings/RoleManagement';

const SettingsComponent: React.FC = () => {
    return (
        <Box sx={{ maxWidth: 1200, margin: '0 auto' }}>
            <Routes>
                <Route path="profile" element={<ProfilePage />} />
                <Route path="connectors" element={<ConnectorsPage />} />
                <Route path="users" element={<UserManagement />} />
                <Route path="roles" element={<RoleManagement />} />
                <Route path="/" element={<Navigate to="profile" replace />} />
                <Route path="*" element={<Navigate to="profile" replace />} />
            </Routes>
        </Box>
    );
};

export default SettingsComponent;
