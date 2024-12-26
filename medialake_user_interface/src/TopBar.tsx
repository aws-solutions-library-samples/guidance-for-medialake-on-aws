import React, { useState, useCallback, useEffect } from 'react';
import {
    AppBar,
    Toolbar,
    IconButton,
    Typography,
    Box,
    Menu,
    MenuItem,
    Tooltip,
    Avatar,
    useTheme as useMuiTheme,
    InputBase,
    Chip,
    Theme,
    SxProps,
} from '@mui/material';
import { Button } from '@/components/common';
import {
    Search as SearchIcon,
    Brightness4 as DarkModeIcon,
    Brightness7 as LightModeIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import debounce from 'lodash/debounce';
import { signOut, fetchUserAttributes } from 'aws-amplify/auth';
import { useAuth } from './common/hooks/auth-context';
import { useTranslation } from 'react-i18next';
import { useTheme } from './hooks/useTheme';

interface SearchTag {
    key: string;
    value: string;
}

const languages = {
    en: { nativeName: 'English' },
    de: { nativeName: 'Deutsch' }
};

function TopBar() {
    const muiTheme = useMuiTheme();
    const { theme, toggleTheme } = useTheme();
    const navigate = useNavigate();
    const { setIsAuthenticated } = useAuth();
    const { t, i18n } = useTranslation();
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
    const [languageAnchor, setLanguageAnchor] = useState<null | HTMLElement>(null);
    const [searchInput, setSearchInput] = useState('');
    const [searchTags, setSearchTags] = useState<SearchTag[]>([]);
    const [userInitial, setUserInitial] = useState('U');

    useEffect(() => {
        const loadUserInitial = async () => {
            try {
                const attributes = await fetchUserAttributes();
                if (attributes.name && attributes.name.trim()) {
                    setUserInitial(attributes.name.trim()[0].toUpperCase());
                } else if (attributes.email && attributes.email.trim()) {
                    setUserInitial(attributes.email.trim()[0].toUpperCase());
                }
            } catch (error) {
                console.error('Error loading user attributes:', error);
            }
        };
        loadUserInitial();
    }, []);

    const getSearchQuery = useCallback(() => {
        const tagPart = searchTags.map(tag => `${tag.key}: ${tag.value}`).join(' ');
        return `${tagPart}${tagPart && searchInput ? ' ' : ''}${searchInput}`.trim();
    }, [searchTags, searchInput]);

    const debouncedSearch = useCallback(
        debounce((query: string) => {
            if (query.trim()) {
                navigate('/search', { state: { query } });
            }
        }, 500),
        [navigate]
    );

    const handleProfileClick = (event: React.MouseEvent<HTMLElement>) => {
        setAnchorEl(event.currentTarget);
    };

    const handleClose = () => {
        setAnchorEl(null);
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
            navigate('/sign-in');
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
        setSearchInput(value);

        if (value.endsWith(' ') && value.includes(':')) {
            const potentialTag = value.trim();
            if (createTagFromInput(potentialTag)) {
                return;
            }
        }

        if (!value.includes(':')) {
            const currentQuery = value.trim() ?
                `${searchTags.map(tag => `${tag.key}: ${tag.value}`).join(' ')}${searchTags.length > 0 ? ' ' : ''}${value}` :
                searchTags.map(tag => `${tag.key}: ${tag.value}`).join(' ');
            debouncedSearch(currentQuery);
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

    const menuPaperStyles: SxProps<Theme> = {
        mt: 1.5,
        boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
    };

    const profileMenuPaperStyles: SxProps<Theme> = {
        width: '200px',
        mt: 1.5,
        boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
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
                            onKeyUp={handleSearchKeyPress}
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
                        sx={{ minWidth: '80px' }}
                    >
                        {t('common.search')}
                    </Button>
                </Box>

                {/* Right section */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    {/* Theme Toggle Button */}
                    <Tooltip title={theme === 'light' ? t('common.darkMode') : t('common.lightMode')}>
                        <IconButton onClick={toggleTheme}>
                            {theme === 'light' ?
                                <DarkModeIcon sx={{ color: 'action.active' }} /> :
                                <LightModeIcon sx={{ color: 'white' }} />
                            }
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
                                {userInitial}
                            </Avatar>
                        </IconButton>
                    </Tooltip>
                </Box>

                {/* Menus */}
                <Menu
                    anchorEl={languageAnchor}
                    open={Boolean(languageAnchor)}
                    onClose={handleClose}
                    slotProps={{
                        paper: {
                            sx: menuPaperStyles
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
                    anchorEl={anchorEl}
                    open={Boolean(anchorEl)}
                    onClose={handleClose}
                    slotProps={{
                        paper: {
                            sx: profileMenuPaperStyles
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
