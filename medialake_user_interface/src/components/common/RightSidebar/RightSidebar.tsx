import React, { ReactNode } from 'react';
import { Box, Button } from '@mui/material';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { useRightSidebar } from './SidebarContext';

interface RightSidebarProps {
    children: ReactNode;
}

export const RightSidebar: React.FC<RightSidebarProps> = ({ children }) => {
    const { isExpanded, setIsExpanded } = useRightSidebar();

    return (
        <>
            <Box sx={{
                width: isExpanded ? 240 : 48,
                flexShrink: 0,
                borderLeft: '1px solid',
                borderColor: 'divider',
                transition: theme => theme.transitions.create(['width'], {
                    easing: theme.transitions.easing.sharp,
                    duration: theme.transitions.duration.enteringScreen,
                }),
                overflowX: 'hidden',
                bgcolor: '#fff',
                position: 'fixed',
                top: 64,
                right: 0,
                height: 'calc(100vh - 64px)',
                display: 'flex',
                flexDirection: 'column',
                zIndex: 1000
            }}>
                <Box sx={{
                    position: 'absolute',
                    left: -20,
                    top: '50%',
                    transform: 'translateY(-50%)',
                    zIndex: 1001
                }}>
                    <Button
                        variant="text"
                        onClick={() => setIsExpanded(!isExpanded)}
                        startIcon={
                            <ChevronRightIcon
                                sx={{
                                    transform: isExpanded ? 'rotate(0deg)' : 'rotate(180deg)',
                                    transition: theme => theme.transitions.create('transform', {
                                        duration: theme.transitions.duration.shortest,
                                    }),
                                }}
                            />
                        }
                        sx={{
                            minWidth: 'unset',
                            width: '40px',
                            p: 0,
                            bgcolor: 'background.paper',
                            borderRadius: '50%',
                            boxShadow: 1,
                            '&:hover': {
                                bgcolor: 'background.paper',
                            }
                        }}
                    />
                </Box>
                <Box sx={{
                    width: '100%',
                    height: '100%',
                    overflowY: 'auto',
                    visibility: isExpanded ? 'visible' : 'hidden'
                }}>
                    {children}
                </Box>
            </Box>

            {/* Spacer to prevent content from going under the fixed sidebar */}
            <Box sx={{ width: isExpanded ? 240 : 48, flexShrink: 0 }} />
        </>
    );
};

export default RightSidebar;
