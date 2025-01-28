import React from 'react';
import { Box, useTheme } from '@mui/material';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useSidebar } from '../../contexts/SidebarContext';
import ConnectorsPage from '../../pages/settings/ConnectorsPage';
import ProfilePage from '../../pages/settings/ProfilePage';
import UserManagement from '../../pages/settings/UserManagement';
import RoleManagement from '../../pages/settings/RoleManagement';
import IntegrationsPage from '../../pages/settings/IntegrationsPage';
import EnvironmentsPage from '../../pages/settings/EnvironmentsPage';

const SettingsComponent: React.FC = () => {
    const { isCollapsed } = useSidebar();
    const theme = useTheme();

    return (
        <Box sx={{
            width: `calc(100% - ${40}px)`, // 20px padding on each side
            maxWidth: `calc(100vw - ${isCollapsed ? 72 : 260}px - ${80}px)`, // sidebar width + total padding (40px on each side)
            margin: '0 auto',
            px: 3,
            transition: theme.transitions.create(['max-width', 'width'], {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.enteringScreen,
            })
        }}>
            <Routes>
                <Route path="profile" element={<ProfilePage />} />
                <Route path="connectors" element={<ConnectorsPage />} />
                <Route path="users" element={<UserManagement />} />
                <Route path="roles" element={<RoleManagement />} />
                <Route path="integrations" element={<IntegrationsPage />} />
                <Route path="environments" element={<EnvironmentsPage />} />
                <Route path="/" element={<Navigate to="profile" replace />} />
                <Route path="*" element={<Navigate to="profile" replace />} />
            </Routes>
        </Box>
    );
};

export default SettingsComponent;
