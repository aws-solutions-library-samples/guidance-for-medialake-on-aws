import React, { ReactNode } from 'react';
import { Box, Button } from '@mui/material';
import { ChevronLeft, ChevronRight } from '@mui/icons-material';
import { useRightSidebar } from './SidebarContext';
import { useLocation } from 'react-router-dom';

interface RightSidebarProps {
    children: ReactNode;
}

export const RightSidebar: React.FC<RightSidebarProps> = ({ children }) => {
    const { isExpanded, setIsExpanded } = useRightSidebar();
    const location = useLocation();

    // Auto-close on search page
    React.useEffect(() => {
        if (location.pathname === '/search') {
            setIsExpanded(false);
        }
    }, [location.pathname, setIsExpanded]);

    return (
        <>
            <Box
                sx={{
                    width: isExpanded ? 300 : 8,
                    flexShrink: 0,
                    borderLeft: '1px solid',
                    borderColor: 'divider',
                    transition: theme => theme.transitions.create(['width'], {
                        easing: theme.transitions.easing.sharp,
                        duration: theme.transitions.duration.enteringScreen,
                    }),
                    bgcolor: 'background.paper',
                    position: 'fixed',
                    top: 64,
                    right: 0,
                    height: 'calc(100vh - 64px)',
                    display: 'flex',
                    flexDirection: 'column',
                    zIndex: 1200
                }}
            >
                <Box
                    sx={{
                        position: 'absolute',
                        top: 0,
                        height: '100%',
                        overflowX: 'hidden',
                        width: '100%',
                    }}
                >
                    <Box sx={{
                        width: '100%',
                        height: '100%',
                        overflowY: 'auto',
                        visibility: isExpanded ? 'visible' : 'hidden'
                    }}>
                        {children}
                    </Box>
                </Box>

                <Button
                    onClick={() => setIsExpanded(!isExpanded)}
                    sx={{
                        position: 'absolute',
                        left: -12,
                        top: '50%',
                        transform: 'translateY(-50%)',
                        minWidth: '24px',
                        width: '24px',
                        height: '24px',
                        bgcolor: 'background.paper',
                        borderRadius: '8px',
                        boxShadow: '0px 2px 4px rgba(0, 0, 0, 0.1)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        border: '1px solid',
                        borderColor: 'divider',
                        zIndex: 1201,
                        padding: 0,
                        '&:hover': {
                            bgcolor: 'background.paper',
                            boxShadow: '0px 4px 8px rgba(0, 0, 0, 0.1)',
                        },
                    }}
                >
                    {isExpanded ? (
                        <ChevronRight sx={{ fontSize: 16 }} />
                    ) : (
                        <ChevronLeft sx={{ fontSize: 16 }} />
                    )}
                </Button>
            </Box>

            <Box sx={{ width: isExpanded ? 300 : 8, flexShrink: 0 }} />
        </>
    );
};

export default RightSidebar;
