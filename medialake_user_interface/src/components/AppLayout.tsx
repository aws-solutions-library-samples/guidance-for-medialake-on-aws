import React, { useState } from 'react';
import { drawerWidth, collapsedDrawerWidth } from '@/constants';
import { Box } from '@mui/material';
import { Outlet } from 'react-router-dom';
import { SidebarContext } from '../contexts/SidebarContext';
import { useDirection } from '../contexts/DirectionContext';
import TopBar from '../TopBar';
import Sidebar from '../Sidebar';

const AppLayout: React.FC = () => {
    const [isCollapsed, setIsCollapsed] = useState(false);
    const { direction } = useDirection();
    const isRTL = direction === 'rtl';

    return (
        <SidebarContext.Provider value={{ isCollapsed, setIsCollapsed }}>
            <Box sx={{ display: 'flex', flexDirection: isRTL ? 'row-reverse' : 'row' }}>
                <Sidebar />
                <Box
                    component="main"
                    sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        width: '100%',
                        [isRTL ? 'marginRight' : 'marginLeft']: `${isCollapsed ? collapsedDrawerWidth : drawerWidth}px`,
                        position: 'relative',
                        minHeight: '100vh',
                    }}
                >
                    <Box sx={{
                        position: 'fixed',
                        top: 0,
                        right: 0,
                        left: 0,
                        height: '64px',
                        [isRTL ? 'paddingRight' : 'paddingLeft']: `${isCollapsed ? collapsedDrawerWidth : drawerWidth}px`,
                        zIndex: 1100,
                        bgcolor: theme => theme.palette.background.default,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                    }}>
                        <Box sx={{
                            width: '100%',
                            maxWidth: '800px',
                            mx: 'auto',
                            px: 2,
                        }}>
                            <TopBar />
                        </Box>
                    </Box>
                    <Box sx={{
                        flexGrow: 1,
                        p: 4,
                        mt: '64px',
                        display: 'flex',
                        flexDirection: 'column',
                        minWidth: 0,
                        overflow: 'auto',
                        backgroundColor: theme => theme.palette.background.default
                    }}>
                        <Outlet />
                    </Box>
                </Box>
            </Box>
        </SidebarContext.Provider>
    );
};

export default AppLayout;
