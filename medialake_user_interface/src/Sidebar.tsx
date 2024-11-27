import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
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
} from '@mui/material';
import {
    AccountTree as PipelineIcon,
    Reviews as ReviewIcon,
    Settings as SettingsIcon,
    ExpandLess,
    ExpandMore,
    Storage as StorageIcon,
    Api as ApiIcon,
    AdminPanelSettings as AdminIcon,
    PermMedia as MediaAssetsIcon,
    DataObject as MetadataIcon,
    LocalOffer as TagsIcon,
    PlaylistPlay as ExecutionsIcon,
    ChevronLeft as ChevronLeftIcon,
    Menu as MenuIcon,
    Group as GroupIcon,
    Security as SecurityIcon,
    Home as HomeIcon,
} from '@mui/icons-material';
import { useLocation, useNavigate, Link as RouterLink } from 'react-router-dom';
import { useTheme as useCustomTheme } from './hooks/useTheme';

const drawerWidth = 260;
const collapsedDrawerWidth = 72;

function Sidebar() {
    const { t } = useTranslation();
    const theme = useTheme();
    const { theme: customTheme } = useCustomTheme();
    const location = useLocation();
    const navigate = useNavigate();
    const [settingsOpen, setSettingsOpen] = useState(false);
    const [isCollapsed, setIsCollapsed] = useState(false);

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
            text: t('sidebar.menu.metadata'),
            icon: <MetadataIcon />,
            path: '/metadata'
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
            text: t('sidebar.menu.reviewQueue'),
            icon: <ReviewIcon />,
            path: '/review-queue'
        },
        {
            text: t('sidebar.menu.tags'),
            icon: <TagsIcon />,
            path: '/tags'
        },
        {
            text: t('sidebar.menu.settings'),
            icon: <SettingsIcon />,
            onClick: () => setSettingsOpen(!settingsOpen),
            isExpandable: true,
            isExpanded: settingsOpen,
            subItems: [
                { text: t('sidebar.submenu.integrations'), icon: <ApiIcon />, path: '/settings/integrations' },
                { text: t('sidebar.submenu.connectors'), icon: <StorageIcon />, path: '/settings/connectors' },
                { text: t('sidebar.submenu.userManagement'), icon: <GroupIcon />, path: '/settings/users' },
                { text: t('sidebar.submenu.roles'), icon: <SecurityIcon />, path: '/settings/roles' },
                { text: t('sidebar.submenu.system'), icon: <AdminIcon />, path: '/settings/system' },
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
                transition: theme.transitions.create('width', {
                    easing: theme.transitions.easing.sharp,
                    duration: theme.transitions.duration.enteringScreen,
                }),
                '& .MuiDrawer-paper': {
                    width: isCollapsed ? collapsedDrawerWidth : drawerWidth,
                    boxSizing: 'border-box',
                    borderRight: '1px solid rgba(0,0,0,0.08)',
                    backgroundColor: theme.palette.background.paper,
                    mt: '64px', // Height of TopBar
                    transition: theme.transitions.create('width', {
                        easing: theme.transitions.easing.sharp,
                        duration: theme.transitions.duration.enteringScreen,
                    }),
                    overflowX: 'hidden',
                },
            }}
        >
            <Box sx={{ overflow: 'auto', py: 2 }}>
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', px: 1, mb: 1 }}>
                    <IconButton onClick={toggleDrawer}>
                        {isCollapsed ? (
                            <MenuIcon sx={{ color: customTheme === 'dark' ? 'white' : 'inherit' }} />
                        ) : (
                            <ChevronLeftIcon sx={{ color: customTheme === 'dark' ? 'white' : 'inherit' }} />
                        )}
                    </IconButton>
                </Box>
                <List>
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
                                                        backgroundColor: isSettingsActive(subItem.text.toLowerCase())
                                                            ? `${theme.palette.primary.main}08`
                                                            : 'transparent',
                                                        '&:hover': {
                                                            backgroundColor: `${theme.palette.primary.main}15`,
                                                        },
                                                        borderRight: isSettingsActive(subItem.text.toLowerCase())
                                                            ? `3px solid ${theme.palette.primary.main}`
                                                            : 'none',
                                                        mx: 1,
                                                        borderRadius: '8px',
                                                    }}
                                                >
                                                    <ListItemIcon sx={{
                                                        color: getIconColor(isSettingsActive(subItem.text.toLowerCase())),
                                                        minWidth: '40px'
                                                    }}>
                                                        {subItem.icon}
                                                    </ListItemIcon>
                                                    <ListItemText
                                                        primary={
                                                            <Typography
                                                                variant="body2"
                                                                sx={{
                                                                    fontWeight: isSettingsActive(subItem.text.toLowerCase()) ? 600 : 400,
                                                                    color: isSettingsActive(subItem.text.toLowerCase())
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
            </Box>
        </Drawer>
    );
}

export default Sidebar;
