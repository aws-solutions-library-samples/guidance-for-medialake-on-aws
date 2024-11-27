{/* Previous imports remain the same */ }
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
    useTheme as useMuiTheme,
    Divider,
    InputBase,
    Chip,
    Button,
    Select,
    SelectChangeEvent,
} from '@mui/material';
import {
    Notifications as NotificationsIcon,
    Search as SearchIcon,
    Warning as WarningIcon,
    Error as ErrorIcon,
    Info as InfoIcon,
    Language as LanguageIcon,
    Brightness4 as DarkModeIcon,
    Brightness7 as LightModeIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useSearch } from './api/hooks/useSearch';
import debounce from 'lodash/debounce';
import { signOut } from 'aws-amplify/auth';
import { useAuth } from './common/hooks/auth-context';
import { useTranslation } from 'react-i18next';
import { useTheme } from './hooks/useTheme';

{/* Previous interfaces and mock data remain the same */ }
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

const languages = {
    en: { nativeName: 'English' },
    de: { nativeName: 'Deutsch' }
};

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
    const muiTheme = useMuiTheme();
    const { theme, toggleTheme } = useTheme();
    const navigate = useNavigate();
    const { setIsAuthenticated } = useAuth();
    const { t, i18n } = useTranslation();
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
    const [notificationsAnchor, setNotificationsAnchor] = useState<null | HTMLElement>(null);
    const [languageAnchor, setLanguageAnchor] = useState<null | HTMLElement>(null);
    const [searchInput, setSearchInput] = useState('');
    const [searchTags, setSearchTags] = useState<SearchTag[]>([]);

    {/* Previous functions remain the same */ }
    const getSearchQuery = useCallback(() => {
        const tagPart = searchTags.map(tag => `${tag.key}: ${tag.value}`).join(' ');
        return `${tagPart}${tagPart && searchInput ? ' ' : ''}${searchInput}`.trim();
    }, [searchTags, searchInput]);

    const { data: searchResults } = useSearch(getSearchQuery() || '');

    const debouncedSearch = useCallback(
        debounce((query: string) => {
            if (query.trim()) {
                navigate('/search', { state: { query: getSearchQuery() } });
            }
        }, 500),
        [navigate, getSearchQuery]
    );

    const handleProfileClick = (event: React.MouseEvent<HTMLElement>) => {
        setAnchorEl(event.currentTarget);
    };

    const handleLanguageClick = (event: React.MouseEvent<HTMLElement>) => {
        setLanguageAnchor(event.currentTarget);
    };

    const handleNotificationsClick = (event: React.MouseEvent<HTMLElement>) => {
        setNotificationsAnchor(event.currentTarget);
    };

    const handleClose = () => {
        setAnchorEl(null);
        setNotificationsAnchor(null);
        setLanguageAnchor(null);
    };

    const handleLanguageChange = (lng: string) => {
        i18n.changeLanguage(lng);
        handleClose();
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
        }
    };

    const handleDeleteTag = (tagToDelete: SearchTag) => {
        setSearchTags(prev => {
            const newTags = prev.filter(tag =>
                !(tag.key === tagToDelete.key && tag.value === tagToDelete.value)
            );
            const searchQuery = newTags.map(tag => `${tag.key}: ${tag.value}`).join(' ');
            navigate('/search', { state: { query: searchQuery } });
            return newTags;
        });
    };

    const getNotificationIcon = (type: string) => {
        switch (type) {
            case 'alert':
                return <ErrorIcon sx={{ color: muiTheme.palette.error.main }} />;
            case 'warning':
                return <WarningIcon sx={{ color: muiTheme.palette.warning.main }} />;
            default:
                return <InfoIcon sx={{ color: muiTheme.palette.info.main }} />;
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
                    {t(notification.title)}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                    {t(notification.message)}
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
                zIndex: muiTheme.zIndex.drawer + 1,
                backgroundColor: theme === 'dark' ? muiTheme.palette.background.default : 'white',
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
                        style={{ height: '32px', marginRight: muiTheme.spacing(1) }}
                    />
                    <Typography
                        variant="h6"
                        sx={{
                            fontWeight: 600,
                            color: muiTheme.palette.primary.main,
                            marginRight: muiTheme.spacing(2)
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
                                backgroundColor: muiTheme.palette.primary.light,
                                color: muiTheme.palette.primary.contrastText,
                                '& .MuiChip-deleteIcon': {
                                    color: muiTheme.palette.primary.contrastText,
                                },
                            }}
                        />
                    ))}

                    {/* Search Input */}
                    <Box sx={{
                        display: 'flex',
                        alignItems: 'center',
                        backgroundColor: theme === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.04)',
                        borderRadius: '8px',
                        padding: '4px 12px',
                        flex: 1,
                    }}>
                        <SearchIcon sx={{
                            color: theme === 'dark' ? 'rgba(255,255,255,0.7)' : 'text.secondary',
                            mr: 1
                        }} />
                        <InputBase
                            placeholder={t('common.search')}
                            value={searchInput}
                            onChange={handleSearchInputChange}
                            onKeyPress={handleSearchKeyPress}
                            fullWidth
                            sx={{
                                fontSize: '14px',
                                color: theme === 'dark' ? 'white' : muiTheme.palette.text.primary,
                                '& input': {
                                    padding: '4px 0',
                                    '&::placeholder': {
                                        color: theme === 'dark' ? 'rgba(255,255,255,0.7)' : 'inherit',
                                        opacity: 1,
                                    },
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
                            backgroundColor: muiTheme.palette.primary.main,
                            '&:hover': {
                                backgroundColor: muiTheme.palette.primary.dark,
                            },
                        }}
                    >
                        {t('common.search')}
                    </Button>
                </Box>

                {/* Right section */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Box sx={{ display: 'flex', gap: 1 }}>
                        <Tooltip title={t('common.alerts')}>
                            <IconButton onClick={handleNotificationsClick}>
                                <Badge badgeContent={getNotificationCount('alert')} color="error">
                                    <ErrorIcon color="error" />
                                </Badge>
                            </IconButton>
                        </Tooltip>
                        <Tooltip title={t('common.warnings')}>
                            <IconButton onClick={handleNotificationsClick}>
                                <Badge badgeContent={getNotificationCount('warning')} color="warning">
                                    <WarningIcon color="warning" />
                                </Badge>
                            </IconButton>
                        </Tooltip>
                        <Tooltip title={t('common.notifications')}>
                            <IconButton onClick={handleNotificationsClick}>
                                <Badge badgeContent={getNotificationCount('notification')} color="info">
                                    <NotificationsIcon sx={{ color: theme === 'dark' ? 'white' : 'action.active' }} />
                                </Badge>
                            </IconButton>
                        </Tooltip>
                    </Box>

                    {/* Theme Toggle Button */}
                    <Tooltip title={theme === 'light' ? t('common.darkMode') : t('common.lightMode')}>
                        <IconButton onClick={toggleTheme}>
                            {theme === 'light' ?
                                <DarkModeIcon sx={{ color: 'action.active' }} /> :
                                <LightModeIcon sx={{ color: 'white' }} />
                            }
                        </IconButton>
                    </Tooltip>

                    {/* Language Selector */}
                    <Tooltip title={t('common.language')}>
                        <IconButton onClick={handleLanguageClick}>
                            <LanguageIcon sx={{ color: theme === 'dark' ? 'white' : 'action.active' }} />
                        </IconButton>
                    </Tooltip>

                    <Tooltip title={t('common.profile')}>
                        <IconButton onClick={handleProfileClick} sx={{ padding: 0.5 }}>
                            <Avatar
                                sx={{
                                    width: 32,
                                    height: 32,
                                    backgroundColor: muiTheme.palette.primary.main,
                                }}
                            >
                                A
                            </Avatar>
                        </IconButton>
                    </Tooltip>
                </Box>

                {/* Menus remain the same */}
                <Menu
                    anchorEl={languageAnchor}
                    open={Boolean(languageAnchor)}
                    onClose={handleClose}
                    PaperProps={{
                        sx: {
                            mt: 1.5,
                            boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                        }
                    }}
                >
                    {Object.keys(languages).map((lng) => (
                        <MenuItem
                            key={lng}
                            onClick={() => handleLanguageChange(lng)}
                            sx={{
                                fontWeight: i18n.resolvedLanguage === lng ? 'bold' : 'normal'
                            }}
                        >
                            {languages[lng as keyof typeof languages].nativeName}
                        </MenuItem>
                    ))}
                </Menu>

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
                        {t('common.profile')}
                    </MenuItem>
                    <MenuItem onClick={handleLogout} sx={{ color: 'error.main' }}>
                        {t('common.logout')}
                    </MenuItem>
                </Menu>
            </Toolbar>
        </AppBar>
    );
}

export default TopBar;
