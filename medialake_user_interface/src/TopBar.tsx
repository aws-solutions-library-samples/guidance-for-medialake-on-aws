import React, { useState } from 'react';
import {
    AppBar,
    Toolbar,
    IconButton,
    Typography,
    Box,
    Menu,
    MenuItem,
    Badge,
    Tooltip,
    Avatar,
    useTheme,
    Divider,
} from '@mui/material';
import {
    Notifications as NotificationsIcon,
    Search as SearchIcon,
    Warning as WarningIcon,
    Error as ErrorIcon,
    Info as InfoIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';

interface Notification {
    id: string;
    type: 'notification' | 'warning' | 'alert';
    title: string;
    message: string;
    timestamp: string;
}

const mockNotifications: Notification[] = [
    {
        id: '1',
        type: 'notification',
        title: 'Pipeline Complete',
        message: 'Asset processing pipeline completed successfully',
        timestamp: '2 min ago'
    },
    {
        id: '2',
        type: 'warning',
        title: 'Storage Warning',
        message: 'Storage capacity reaching 80%',
        timestamp: '10 min ago'
    },
    {
        id: '3',
        type: 'alert',
        title: 'Pipeline Failed',
        message: 'Video processing pipeline failed',
        timestamp: '15 min ago'
    }
];

function TopBar() {
    const theme = useTheme();
    const navigate = useNavigate();
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
    const [notificationsAnchor, setNotificationsAnchor] = useState<null | HTMLElement>(null);

    const handleProfileClick = (event: React.MouseEvent<HTMLElement>) => {
        setAnchorEl(event.currentTarget);
    };

    const handleNotificationsClick = (event: React.MouseEvent<HTMLElement>) => {
        setNotificationsAnchor(event.currentTarget);
    };

    const handleClose = () => {
        setAnchorEl(null);
        setNotificationsAnchor(null);
    };

    const getNotificationIcon = (type: string) => {
        switch (type) {
            case 'alert':
                return <ErrorIcon sx={{ color: theme.palette.error.main }} />;
            case 'warning':
                return <WarningIcon sx={{ color: theme.palette.warning.main }} />;
            default:
                return <InfoIcon sx={{ color: theme.palette.info.main }} />;
        }
    };

    const getNotificationCount = (type: string) => {
        return mockNotifications.filter(n => n.type === type).length;
    };

    return (
        <AppBar
            position="fixed"
            sx={{
                zIndex: theme.zIndex.drawer + 1,
                backgroundColor: 'white',
                color: 'text.primary',
                boxShadow: '0 1px 3px rgba(0,0,0,0.12)',
            }}
        >
            <Toolbar sx={{ justifyContent: 'space-between' }}>
                {/* Left section */}
                <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    <img
                        src="/logo.png"
                        alt="MediaLake"
                        style={{ height: '32px', marginRight: theme.spacing(2) }}
                    />
                </Box>

                {/* Center section - Search */}
                <Box sx={{
                    display: 'flex',
                    alignItems: 'center',
                    backgroundColor: 'rgba(0,0,0,0.04)',
                    borderRadius: '8px',
                    padding: '4px 12px',
                    width: '400px',
                }}>
                    <SearchIcon sx={{ color: 'text.secondary', mr: 1 }} />
                    <input
                        placeholder="Search assets, pipelines, or tags..."
                        style={{
                            border: 'none',
                            backgroundColor: 'transparent',
                            width: '100%',
                            outline: 'none',
                            fontSize: '14px',
                            color: theme.palette.text.primary,
                        }}
                    />
                </Box>

                {/* Right section */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Box sx={{ display: 'flex', gap: 1 }}>
                        <Tooltip title="Alerts">
                            <IconButton onClick={handleNotificationsClick}>
                                <Badge badgeContent={getNotificationCount('alert')} color="error">
                                    <ErrorIcon color="error" />
                                </Badge>
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Warnings">
                            <IconButton onClick={handleNotificationsClick}>
                                <Badge badgeContent={getNotificationCount('warning')} color="warning">
                                    <WarningIcon color="warning" />
                                </Badge>
                            </IconButton>
                        </Tooltip>
                        <Tooltip title="Notifications">
                            <IconButton onClick={handleNotificationsClick}>
                                <Badge badgeContent={getNotificationCount('notification')} color="info">
                                    <NotificationsIcon color="action" />
                                </Badge>
                            </IconButton>
                        </Tooltip>
                    </Box>

                    <Tooltip title="Profile">
                        <IconButton onClick={handleProfileClick} sx={{ padding: 0.5 }}>
                            <Avatar
                                sx={{
                                    width: 32,
                                    height: 32,
                                    backgroundColor: theme.palette.primary.main,
                                }}
                            >
                                A
                            </Avatar>
                        </IconButton>
                    </Tooltip>
                </Box>

                {/* Notifications Menu */}
                <Menu
                    anchorEl={notificationsAnchor}
                    open={Boolean(notificationsAnchor)}
                    onClose={handleClose}
                    PaperProps={{
                        sx: {
                            width: '320px',
                            maxHeight: '400px',
                            mt: 1.5,
                            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                        }
                    }}
                >
                    {mockNotifications.map((notification, index) => (
                        <React.Fragment key={notification.id}>
                            <MenuItem>
                                <Box sx={{ display: 'flex', width: '100%', gap: 1 }}>
                                    <Box sx={{ pt: 0.5 }}>
                                        {getNotificationIcon(notification.type)}
                                    </Box>
                                    <Box sx={{ flex: 1 }}>
                                        <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                                            {notification.title}
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            {notification.message}
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            {notification.timestamp}
                                        </Typography>
                                    </Box>
                                </Box>
                            </MenuItem>
                            {index < mockNotifications.length - 1 && <Divider />}
                        </React.Fragment>
                    ))}
                </Menu>

                {/* Profile Menu */}
                <Menu
                    anchorEl={anchorEl}
                    open={Boolean(anchorEl)}
                    onClose={handleClose}
                    PaperProps={{
                        sx: {
                            width: '200px',
                            mt: 1.5,
                            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                        }
                    }}
                >
                    <MenuItem onClick={() => {
                        handleClose();
                        navigate('/settings/profile');
                    }}>
                        Profile
                    </MenuItem>
                    <MenuItem onClick={handleClose} sx={{ color: 'error.main' }}>
                        Logout
                    </MenuItem>
                </Menu>
            </Toolbar>
        </AppBar>
    );
}

export default TopBar;
