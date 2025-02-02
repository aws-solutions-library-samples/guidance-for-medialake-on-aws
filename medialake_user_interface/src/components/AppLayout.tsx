import React, { useState } from 'react';
import { Box } from '@mui/material';
import { Outlet } from 'react-router-dom';
import { SidebarContext } from '../contexts/SidebarContext';
import TopBar from '../TopBar';
import Sidebar from '../Sidebar';

const AppLayout: React.FC = () => {
    const [isCollapsed, setIsCollapsed] = useState(false);

    return (
        <SidebarContext.Provider value={{ isCollapsed, setIsCollapsed }}>
            <Box sx={{ display: 'flex' }}>
                <TopBar />
                <Sidebar />
                <Box component="main" sx={{
                    flexGrow: 1,
                    mt: 8,
                    display: 'flex',
                    flexDirection: 'column',
                    minWidth: 0,
                    height: 'calc(100vh - 64px)',
                    overflow: 'hidden'
                }}>
                    <Outlet />
                </Box>
            </Box>
        </SidebarContext.Provider>
    );
};

export default AppLayout;