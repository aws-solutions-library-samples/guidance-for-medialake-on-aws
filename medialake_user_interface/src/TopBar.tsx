import React, { useState, useCallback } from 'react';
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
    InputBase,
    Chip,
    Button,
} from '@mui/material';
import {
    Notifications as NotificationsIcon,
    Search as SearchIcon,
    Warning as WarningIcon,
    Error as ErrorIcon,
    Info as InfoIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useSearch } from './api/hooks/useSearch';
import debounce from 'lodash/debounce';
import { signOut } from 'aws-amplify/auth';
import { useAuth } from './common/hooks/auth-context';

interface Notification {
    id: string;
    type: 'notification' | 'warning' | 'alert';
    title: string;
    message: string;
    timestamp: string;
}

interface SearchTag {
    key: string;
    value: string;
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
    const { setIsAuthenticated } = useAuth();
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
    const [notificationsAnchor, setNotificationsAnchor] = useState<null | HTMLElement>(null);
    const [searchInput, setSearchInput] = useState('');
    const [searchTags, setSearchTags] = useState<SearchTag[]>([]);

    const getSearchQuery = useCallback(() => {
        const tagPart = searchTags.map(tag => `${tag.key}: ${tag.value}`).join(' ');
        return `${tagPart}${tagPart && searchInput ? ' ' : ''}${searchInput}`.trim();
    }, [searchTags, searchInput]);

    const { refetch } = useSearch(getSearchQuery());

    const debouncedSearch = useCallback(
        debounce((query: string) => {
            if (query.trim()) {
                refetch();
                navigate('/search', { state: { query: getSearchQuery() } });
            }
        }, 500),
        [navigate, refetch, getSearchQuery]
    );

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

    const handleLogout = async () => {
        try {
            await signOut();
            setIsAuthenticated(false);
            navigate('/auth');
        } catch (error) {
            console.error('Error signing out:', error);
        }
        handleClose();
    };

    const createTagFromInput = (input: string): boolean => {
        if (input.includes(':')) {
            const [key, ...valueParts] = input.split(':');
            const value = valueParts.join(':').trim();

            if (key && value) {
                const newTag: SearchTag = {
                    key: key.trim(),
                    value: value
                };

                setSearchTags(prev => [...prev, newTag]);
                setSearchInput('');

                const searchQuery = getSearchQuery();
                navigate('/search', { state: { query: searchQuery } });
                refetch();
                return true;
            }
        }
        return false;
    };

    const handleSearchInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const value = event.target.value;

        if (value.endsWith(' ') && value.includes(':')) {
            const potentialTag = value.trim();
            if (createTagFromInput(potentialTag)) {
                return;
            }
        }

        setSearchInput(value);

        if (!value.includes(':')) {
            debouncedSearch(value);
        }
    };

    const handleSearchKeyPress = (event: React.KeyboardEvent) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            handleSearchSubmit();
        }
    };

    const handleSearchSubmit = () => {
        if (searchInput.includes(':')) {
            createTagFromInput(searchInput);
        } else if (searchInput.trim() || searchTags.length > 0) {
            const searchQuery = getSearchQuery();
            navigate('/search', { state: { query: searchQuery } });
            refetch();
        }
    };

    const handleDeleteTag = (tagToDelete: SearchTag) => {
        setSearchTags(prev => {
            const newTags = prev.filter(tag =>
                !(tag.key === tagToDelete.key && tag.value === tagToDelete.value)
            );
            const searchQuery = newTags.map(tag => `${tag.key}: ${tag.value}`).join(' ');
            navigate('/search', { state: { query: searchQuery } });
            refetch();
            return newTags;
        });
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

    const renderNotificationContent = (notification: Notification) => (
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
    );

    const renderNotificationItems = () => {
        const items: JSX.Element[] = [];
        mockNotifications.forEach((notification, index) => {
            items.push(
                <MenuItem key={`item-${notification.id}`}>
                    {renderNotificationContent(notification)}
                </MenuItem>
            );
            if (index < mockNotifications.length - 1) {
                items.push(
                    <Divider key={`divider-${notification.id}`} />
                );
            }
        });
        return items;
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
                        style={{ height: '32px', marginRight: theme.spacing(1) }}
                    />
                    <Typography
                        variant="h6"
                        sx={{
                            fontWeight: 600,
                            color: theme.palette.primary.main,
                            marginRight: theme.spacing(2)
                        }}
                    >
                        MediaLake
                    </Typography>
                </Box>

                {/* Center section - Search */}
                <Box sx={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    flex: 1,
                    maxWidth: '800px',
                }}>
                    {/* Tags */}
                    {searchTags.map((tag, index) => (
                        <Chip
                            key={index}
                            label={`${tag.key}: ${tag.value}`}
                            onDelete={() => handleDeleteTag(tag)}
                            size="small"
                            sx={{
                                backgroundColor: theme.palette.primary.light,
                                color: theme.palette.primary.contrastText,
                                '& .MuiChip-deleteIcon': {
                                    color: theme.palette.primary.contrastText,
                                },
                            }}
                        />
                    ))}

                    {/* Search Input */}
                    <Box sx={{
                        display: 'flex',
                        alignItems: 'center',
                        backgroundColor: 'rgba(0,0,0,0.04)',
                        borderRadius: '8px',
                        padding: '4px 12px',
                        flex: 1,
                    }}>
                        <SearchIcon sx={{ color: 'text.secondary', mr: 1 }} />
                        <InputBase
                            placeholder="Search or use key:value..."
                            value={searchInput}
                            onChange={handleSearchInputChange}
                            onKeyPress={handleSearchKeyPress}
                            fullWidth
                            sx={{
                                fontSize: '14px',
                                color: theme.palette.text.primary,
                                '& input': {
                                    padding: '4px 0',
                                },
                            }}
                        />
                    </Box>

                    {/* Search Button */}
                    <Button
                        variant="contained"
                        onClick={handleSearchSubmit}
                        sx={{
                            minWidth: 'unset',
                            px: 3,
                            py: 1,
                            backgroundColor: theme.palette.primary.main,
                            '&:hover': {
                                backgroundColor: theme.palette.primary.dark,
                            },
                        }}
                    >
                        Search
                    </Button>
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
                    {renderNotificationItems()}
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
                    <MenuItem onClick={handleLogout} sx={{ color: 'error.main' }}>
                        Logout
                    </MenuItem>
                </Menu>
            </Toolbar>
        </AppBar>
    );
}

export default TopBar;
