import React, { useState } from 'react';
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
    Search as SearchIcon,
    Folder as AssetsIcon,
    LocalOffer as TagsIcon,
    PlaylistPlay as ExecutionsIcon,
    ChevronLeft as ChevronLeftIcon,
    Menu as MenuIcon,
} from '@mui/icons-material';
import { useLocation, useNavigate } from 'react-router-dom';

const drawerWidth = 260;
const collapsedDrawerWidth = 72;

function Sidebar() {
    const theme = useTheme();
    const location = useLocation();
    const navigate = useNavigate();
    const [settingsOpen, setSettingsOpen] = useState(false);
    const [isCollapsed, setIsCollapsed] = useState(false);

    const isActive = (path: string) => location.pathname === path;
    const isSettingsActive = (path: string) => location.pathname.includes(path);

    const mainMenuItems = [
        {
            text: 'Assets',
            icon: <AssetsIcon />,
            path: '/'
        },
        {
            text: 'Search',
            icon: <SearchIcon />,
            path: '/search'
        },
        {
            text: 'Pipelines',
            icon: <PipelineIcon />,
            path: '/pipelines'
        },
        {
            text: 'Pipeline Executions',
            icon: <ExecutionsIcon />,
            path: '/executions'
        },
        {
            text: 'Review Queue',
            icon: <ReviewIcon />,
            path: '/review-queue'
        },
        {
            text: 'Tags',
            icon: <TagsIcon />,
            path: '/tags'
        },
        {
            text: 'Settings',
            icon: <SettingsIcon />,
            onClick: () => setSettingsOpen(!settingsOpen),
            isExpandable: true,
            isExpanded: settingsOpen,
            subItems: [
                { text: 'Integrations', icon: <ApiIcon />, path: '/settings/integrations' },
                { text: 'Connectors', icon: <StorageIcon />, path: '/settings/connectors' },
                { text: 'System', icon: <AdminIcon />, path: '/settings/system' },
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
                        {isCollapsed ? <MenuIcon /> : <ChevronLeftIcon />}
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
                                                    color: isActive(item.path || '') || (item.isExpandable && item.isExpanded)
                                                        ? theme.palette.primary.main
                                                        : theme.palette.text.secondary,
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
                                            color: isActive(item.path || '') || (item.isExpandable && item.isExpanded)
                                                ? theme.palette.primary.main
                                                : theme.palette.text.secondary,
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
                                                            : theme.palette.text.primary
                                                    }}
                                                >
                                                    {item.text}
                                                </Typography>
                                            }
                                        />
                                        {item.isExpandable && (
                                            item.isExpanded ? <ExpandLess /> : <ExpandMore />
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
                                                        color: isSettingsActive(subItem.text.toLowerCase())
                                                            ? theme.palette.primary.main
                                                            : theme.palette.text.secondary,
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
                                                                        : theme.palette.text.primary
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
