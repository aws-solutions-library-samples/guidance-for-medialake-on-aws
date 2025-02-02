import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { signOut, fetchUserAttributes } from 'aws-amplify/auth';
import { useAuth } from './common/hooks/auth-context';
import {
    Drawer,
    List,
    ListItem,
    ListItemIcon,
    ListItemText,
    ListItemButton,
    Box,
    useTheme,
    Collapse,
    Typography,
    IconButton,
    Tooltip,
    Button,
    Menu,
    MenuItem,
    Avatar,
} from '@mui/material';
import {
    AccountTree as PipelineIcon,
    Settings as SettingsIcon,
    ExpandLess,
    ExpandMore,
    Storage as StorageIcon,
    PermMedia as MediaAssetsIcon,
    PlaylistPlay as ExecutionsIcon,
    ChevronLeft,
    ChevronRight,
    Group as GroupIcon,
    Security as SecurityIcon,
    Home as HomeIcon,
    Extension as IntegrationIcon,
    Cloud as EnvironmentIcon,
} from '@mui/icons-material';
import { useLocation, useNavigate } from 'react-router-dom';
import { useTheme as useCustomTheme } from './hooks/useTheme';
import { useSidebar } from './contexts/SidebarContext';
import { ThemeToggle } from './components/ThemeToggle';

const drawerWidth = 260;
const collapsedDrawerWidth = 72;

function Sidebar() {
    const { t } = useTranslation();
    const theme = useTheme();
    const { theme: customTheme } = useCustomTheme();
    const location = useLocation();
    const navigate = useNavigate();
    const { setIsAuthenticated } = useAuth();
    const [settingsOpen, setSettingsOpen] = useState(false);
    const { isCollapsed, setIsCollapsed } = useSidebar();
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
    const [userInitial, setUserInitial] = useState('U');
    const [userName, setUserName] = useState('');

    useEffect(() => {
        const loadUserInfo = async () => {
            try {
                const attributes = await fetchUserAttributes();
                if (attributes.given_name && attributes.given_name.trim()) {
                    setUserInitial(attributes.given_name.trim()[0].toUpperCase());
                    setUserName(attributes.given_name.trim());
                } else if (attributes.email && attributes.email.trim()) {
                    setUserInitial(attributes.email.trim()[0].toUpperCase());
                    setUserName(attributes.email.trim());
                }
            } catch (error) {
                console.error('Error loading user attributes:', error);
            }
        };
        loadUserInfo();
    }, []);

    const handleProfileClick = (event: React.MouseEvent<HTMLElement>) => {
        setAnchorEl(event.currentTarget);
    };

    const handleClose = () => {
        setAnchorEl(null);
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

    const isActive = (path: string) => location.pathname === path;
    const isSettingsActive = (path: string) => location.pathname.includes(path);

    const getIconColor = (isItemActive: boolean) => {
        if (isItemActive) {
            return theme.palette.primary.main;
        }
        return customTheme === 'dark' ? 'white' : theme.palette.text.secondary;
    };

    const mainMenuItems = [
        {
            text: t('sidebar.menu.home'),
            icon: <HomeIcon />,
            path: '/'
        },
        {
            text: t('sidebar.menu.assets'),
            icon: <MediaAssetsIcon />,
            path: '/assets'
        },
        {
            text: t('sidebar.menu.pipelines'),
            icon: <PipelineIcon />,
            path: '/pipelines'
        },
        {
            text: t('sidebar.menu.pipelineExecutions'),
            icon: <ExecutionsIcon />,
            path: '/executions'
        },
        {
            text: t('sidebar.menu.settings'),
            icon: <SettingsIcon />,
            onClick: () => setSettingsOpen(!settingsOpen),
            isExpandable: true,
            isExpanded: settingsOpen,
            subItems: [
                { text: t('sidebar.submenu.connectors'), icon: <StorageIcon />, path: '/settings/connectors' },
                { text: t('sidebar.submenu.userManagement'), icon: <GroupIcon />, path: '/settings/users' },
                { text: t('sidebar.submenu.roles'), icon: <SecurityIcon />, path: '/settings/roles' },
                { text: t('sidebar.submenu.integrations'), icon: <IntegrationIcon />, path: '/settings/integrations' },
                { text: t('sidebar.submenu.environments'), icon: <EnvironmentIcon />, path: '/settings/environments' },
            ]
        }
    ];

    const handleNavigation = (path: string) => {
        navigate(path);
    };

    const toggleDrawer = () => {
        setIsCollapsed(!isCollapsed);
    };

    return (
        <Drawer
            variant="permanent"
            sx={{
                width: isCollapsed ? collapsedDrawerWidth : drawerWidth,
                flexShrink: 0,
                position: 'relative',
                '& .MuiDrawer-paper': {
                    width: isCollapsed ? collapsedDrawerWidth : drawerWidth,
                    boxSizing: 'border-box',
                    borderRight: '1px solid rgba(0,0,0,0.08)',
                    backgroundColor: theme.palette.background.paper,
                    mt: '64px',
                    overflow: 'visible',
                    position: 'relative',
                },
            }}
        >
            <Box sx={{
                overflowY: 'auto',
                overflow: 'visible',
                py: 2,
                position: 'relative',
                height: 'calc(100vh - 64px)',
                display: 'flex',
                flexDirection: 'column',
            }}>
                <Button
                    onClick={toggleDrawer}
                    sx={{
                        position: 'absolute',
                        right: -12,
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
                        zIndex: 1,
                        padding: 0,
                        '&:hover': {
                            bgcolor: 'background.paper',
                            boxShadow: '0px 4px 8px rgba(0, 0, 0, 0.1)',
                        },
                    }}
                >
                    {isCollapsed ? (
                        <ChevronRight sx={{ fontSize: 16 }} />
                    ) : (
                        <ChevronLeft sx={{ fontSize: 16 }} />
                    )}
                </Button>
                <List sx={{ flex: 1 }}>
                    {mainMenuItems.map((item) => (
                        <React.Fragment key={item.text}>
                            <ListItem disablePadding>
                                {isCollapsed ? (
                                    <Tooltip title={item.text} placement="right">
                                        <ListItemButton
                                            onClick={item.isExpandable ? item.onClick : () => handleNavigation(item.path || '/')}
                                            sx={{
                                                minHeight: 48,
                                                justifyContent: 'center',
                                                px: 2.5,
                                                backgroundColor: isActive(item.path || '') || (item.isExpandable && item.isExpanded)
                                                    ? `${theme.palette.primary.main}08`
                                                    : 'transparent',
                                                '&:hover': {
                                                    backgroundColor: `${theme.palette.primary.main}15`,
                                                },
                                            }}
                                        >
                                            <ListItemIcon
                                                sx={{
                                                    minWidth: 0,
                                                    mr: 'auto',
                                                    justifyContent: 'center',
                                                    color: getIconColor(isActive(item.path || '') || (item.isExpandable && item.isExpanded)),
                                                }}
                                            >
                                                {item.icon}
                                            </ListItemIcon>
                                        </ListItemButton>
                                    </Tooltip>
                                ) : (
                                    <ListItemButton
                                        onClick={item.isExpandable ? item.onClick : () => handleNavigation(item.path || '/')}
                                        sx={{
                                            backgroundColor: isActive(item.path || '') || (item.isExpandable && item.isExpanded)
                                                ? `${theme.palette.primary.main}08`
                                                : 'transparent',
                                            '&:hover': {
                                                backgroundColor: `${theme.palette.primary.main}15`,
                                            },
                                            borderRight: isActive(item.path || '')
                                                ? `3px solid ${theme.palette.primary.main}`
                                                : 'none',
                                            mx: 1,
                                            borderRadius: '8px',
                                        }}
                                    >
                                        <ListItemIcon sx={{
                                            color: getIconColor(isActive(item.path || '') || (item.isExpandable && item.isExpanded)),
                                            minWidth: '40px'
                                        }}>
                                            {item.icon}
                                        </ListItemIcon>
                                        <ListItemText
                                            primary={
                                                <Typography
                                                    variant="body2"
                                                    sx={{
                                                        fontWeight: isActive(item.path || '') || (item.isExpandable && item.isExpanded) ? 600 : 400,
                                                        color: isActive(item.path || '') || (item.isExpandable && item.isExpanded)
                                                            ? theme.palette.primary.main
                                                            : customTheme === 'dark' ? 'white' : theme.palette.text.primary
                                                    }}
                                                >
                                                    {item.text}
                                                </Typography>
                                            }
                                        />
                                        {item.isExpandable && (
                                            <Box sx={{ color: customTheme === 'dark' ? 'white' : 'inherit' }}>
                                                {item.isExpanded ? <ExpandLess /> : <ExpandMore />}
                                            </Box>
                                        )}
                                    </ListItemButton>
                                )}
                            </ListItem>
                            {!isCollapsed && item.isExpandable && item.subItems && (
                                <Collapse in={item.isExpanded} timeout="auto" unmountOnExit>
                                    <List component="div" disablePadding>
                                        {item.subItems.map((subItem) => (
                                            <ListItem key={subItem.text} disablePadding>
                                                <ListItemButton
                                                    onClick={() => handleNavigation(subItem.path)}
                                                    sx={{
                                                        pl: 6,
                                                        backgroundColor: isSettingsActive(subItem.path)
                                                            ? `${theme.palette.primary.main}08`
                                                            : 'transparent',
                                                        '&:hover': {
                                                            backgroundColor: `${theme.palette.primary.main}15`,
                                                        },
                                                        borderRight: isSettingsActive(subItem.path)
                                                            ? `3px solid ${theme.palette.primary.main}`
                                                            : 'none',
                                                        mx: 1,
                                                        borderRadius: '8px',
                                                    }}
                                                >
                                                    <ListItemIcon sx={{
                                                        color: getIconColor(isSettingsActive(subItem.path)),
                                                        minWidth: '40px'
                                                    }}>
                                                        {subItem.icon}
                                                    </ListItemIcon>
                                                    <ListItemText
                                                        primary={
                                                            <Typography
                                                                variant="body2"
                                                                sx={{
                                                                    fontWeight: isSettingsActive(subItem.path) ? 600 : 400,
                                                                    color: isSettingsActive(subItem.path)
                                                                        ? theme.palette.primary.main
                                                                        : customTheme === 'dark' ? 'white' : theme.palette.text.primary
                                                                }}
                                                            >
                                                                {subItem.text}
                                                            </Typography>
                                                        }
                                                    />
                                                </ListItemButton>
                                            </ListItem>
                                        ))}
                                    </List>
                                </Collapse>
                            )}
                        </React.Fragment>
                    ))}
                </List>
                
                {/* Profile Section */}
                <Box sx={{
                    mt: 'auto',
                    mb: 1,
                    mx: isCollapsed ? 1 : 2,
                    borderTop: '1px solid',
                    borderColor: 'divider',
                    pt: 1
                }}>
                    {isCollapsed ? (
                        <Tooltip title={userName || t('common.profile')} placement="right">
                            <IconButton
                                onClick={handleProfileClick}
                                sx={{
                                    width: '100%',
                                    height: 40,
                                    borderRadius: '8px',
                                    '&:hover': {
                                        backgroundColor: `${theme.palette.primary.main}15`,
                                    },
                                }}
                            >
                                <Avatar
                                    sx={{
                                        width: 32,
                                        height: 32,
                                        backgroundColor: theme.palette.primary.main,
                                        fontSize: '0.9rem',
                                    }}
                                >
                                    {userInitial}
                                </Avatar>
                            </IconButton>
                        </Tooltip>
                    ) : (
                        <Button
                            onClick={handleProfileClick}
                            sx={{
                                width: '100%',
                                height: 40,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'flex-start',
                                gap: 1.5,
                                borderRadius: '8px',
                                px: 1.5,
                                '&:hover': {
                                    backgroundColor: `${theme.palette.primary.main}15`,
                                },
                            }}
                        >
                            <Avatar
                                sx={{
                                    width: 32,
                                    height: 32,
                                    backgroundColor: theme.palette.primary.main,
                                    fontSize: '0.9rem',
                                }}
                            >
                                {userInitial}
                            </Avatar>
                            <Typography
                                variant="body2"
                                sx={{
                                    color: customTheme === 'dark' ? 'white' : theme.palette.text.primary,
                                    fontWeight: 500,
                                }}
                            >
                                {userName}
                            </Typography>
                        </Button>
                    )}

                    <Menu
                        anchorEl={anchorEl}
                        open={Boolean(anchorEl)}
                        onClose={handleClose}
                        anchorOrigin={{
                            vertical: 'top',
                            horizontal: 'right',
                        }}
                        transformOrigin={{
                            vertical: 'bottom',
                            horizontal: 'left',
                        }}
                        slotProps={{
                            paper: {
                                sx: {
                                    width: '200px',
                                    mt: -1,
                                    boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                                }
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
                </Box>
                <ThemeToggle isCollapsed={isCollapsed} />
            </Box>
        </Drawer>
    );
}

export default Sidebar;
