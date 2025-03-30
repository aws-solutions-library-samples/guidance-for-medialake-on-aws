import React, { ReactNode, useState, useEffect, useRef } from 'react';
import { Box, Button } from '@mui/material';
import { ChevronLeft, ChevronRight } from '@mui/icons-material';
import { useRightSidebar } from './SidebarContext';
import { useLocation } from 'react-router-dom';
import { alpha } from '@mui/material/styles';

interface RightSidebarProps {
    children: ReactNode;
}

// Default width is now 375px (25% wider than previous 300px)
const DEFAULT_WIDTH = 375;
const MIN_WIDTH = 275;
const MAX_WIDTH = 600;
const COLLAPSED_WIDTH = 8;

export const RightSidebar: React.FC<RightSidebarProps> = ({ children }) => {
    const { isExpanded, setIsExpanded } = useRightSidebar();
    const location = useLocation();
    const [width, setWidth] = useState(DEFAULT_WIDTH);
    const [isResizing, setIsResizing] = useState(false);
    const resizeHandleRef = useRef<HTMLDivElement | null>(null);

    // Load saved width on mount
    useEffect(() => {
        const savedWidth = localStorage.getItem('rightSidebarWidth');
        if (savedWidth) {
            const parsedWidth = parseInt(savedWidth, 10);
            if (!isNaN(parsedWidth) && parsedWidth >= MIN_WIDTH && parsedWidth <= MAX_WIDTH) {
                setWidth(parsedWidth);
            }
        }
    }, []);

    // Save width to localStorage when it changes
    useEffect(() => {
        if (width !== COLLAPSED_WIDTH) {
            localStorage.setItem('rightSidebarWidth', width.toString());
        }
    }, [width]);

    // Auto-close on search page
    useEffect(() => {
        if (location.pathname === '/search') {
            setIsExpanded(false);
        }
    }, [location.pathname, setIsExpanded]);

    // Handle resize start
    const handleResizeStart = (e: React.MouseEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsResizing(true);
    };

    // Handle resizing
    useEffect(() => {
        const handleResize = (e: MouseEvent) => {
            if (isResizing && isExpanded) {
                // Calculate new width based on mouse position
                const newWidth = window.innerWidth - e.clientX;
                
                // Apply constraints
                if (newWidth >= MIN_WIDTH && newWidth <= MAX_WIDTH) {
                    setWidth(newWidth);
                }
            }
        };

        const handleResizeEnd = () => {
            setIsResizing(false);
        };

        if (isResizing) {
            document.addEventListener('mousemove', handleResize);
            document.addEventListener('mouseup', handleResizeEnd);
        }

        return () => {
            document.removeEventListener('mousemove', handleResize);
            document.removeEventListener('mouseup', handleResizeEnd);
        };
    }, [isResizing, isExpanded]);

    return (
        <>
            {/* Main sidebar container */}
            <Box
                sx={{
                    width: isExpanded ? width : COLLAPSED_WIDTH,
                    flexShrink: 0,
                    borderLeft: '1px solid',
                    borderColor: 'divider',
                    transition: isResizing ? 'none' : theme => theme.transitions.create(['width', 'border-radius'], {
                        easing: theme.transitions.easing.sharp,
                        duration: theme.transitions.duration.enteringScreen,
                    }),
                    bgcolor: 'background.paper',
                    position: 'fixed',
                    top: 72,
                    right: 0,
                    height: 'calc(100vh - 88px)',
                    display: 'flex',
                    flexDirection: 'column',
                    zIndex: 1200,
                    borderRadius: '16px 0 0 16px',
                    boxShadow: theme => isExpanded ? 
                        `0 4px 20px ${alpha(theme.palette.common.black, 0.1)}` : 'none',
                    overflow: 'hidden',
                }}
            >
                {/* Resize handle */}
                {isExpanded && (
                    <Box
                        ref={resizeHandleRef}
                        onMouseDown={handleResizeStart}
                        sx={{
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            width: '8px',
                            height: '100%',
                            cursor: 'col-resize',
                            zIndex: 1300,
                            '&:hover': {
                                backgroundColor: theme => alpha(theme.palette.primary.main, 0.1),
                            },
                            '&::after': {
                                content: '""',
                                position: 'absolute',
                                top: '50%',
                                left: '3px',
                                width: '2px',
                                height: '40px',
                                backgroundColor: theme => alpha(theme.palette.primary.main, 0.3),
                                borderRadius: '2px',
                                transform: 'translateY(-50%)',
                            }
                        }}
                    />
                )}

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
                        visibility: isExpanded ? 'visible' : 'hidden',
                        py: 2
                    }}>
                        {children}
                    </Box>
                </Box>
            </Box>

            {/* Toggle button - positioned outside the main container to avoid being clipped */}
            <Button
                onClick={() => setIsExpanded(!isExpanded)}
                sx={{
                    position: 'fixed',
                    right: isExpanded ? width - 16 : COLLAPSED_WIDTH - 16,
                    top: 'calc(50vh - 16px)',
                    minWidth: '32px',
                    width: '32px',
                    height: '32px',
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
                    transition: isResizing ? 'none' : theme => theme.transitions.create(['right'], {
                        easing: theme.transitions.easing.sharp,
                        duration: theme.transitions.duration.enteringScreen,
                    }),
                    '&:hover': {
                        bgcolor: 'background.paper',
                        boxShadow: '0px 4px 8px rgba(0, 0, 0, 0.1)',
                    },
                }}
            >
                {isExpanded ? (
                    <ChevronRight sx={{ fontSize: 20 }} />
                ) : (
                    <ChevronLeft sx={{ fontSize: 20 }} />
                )}
            </Button>

            {/* Spacer to maintain layout */}
            <Box sx={{ width: isExpanded ? width : COLLAPSED_WIDTH, flexShrink: 0 }} />

            {/* Optional overlay for better UX during resizing */}
            {isResizing && (
                <Box
                    sx={{
                        position: 'fixed',
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        zIndex: 1199,
                        cursor: 'col-resize',
                    }}
                />
            )}
        </>
    );
};

export default RightSidebar;
