import React, { useState } from 'react';
import { Drawer, List, ListItem, ListItemIcon, ListItemText, IconButton, Box, ListItemButton } from '@mui/material';
import { Menu as MenuIcon, AccountCircle as AccountCircleIcon, Settings as SettingsIcon } from '@mui/icons-material';
import { Link } from 'react-router-dom';
import QueuePlayNextIcon from '@mui/icons-material/QueuePlayNext';
import SearchIcon from '@mui/icons-material/Search';
import DashboardIcon from '@mui/icons-material/Dashboard';
import LabelIcon from '@mui/icons-material/Label';
import TimelineIcon from '@mui/icons-material/Timeline';
import HistoryIcon from '@mui/icons-material/History';
import { useQueryClient } from '@tanstack/react-query';  // Fix the import path

interface MenuItem {
    text: string;
    icon: JSX.Element;
    path: string;
}

const menuItems: MenuItem[] = [
    { text: 'Search', icon: <SearchIcon />, path: '/search' },
    { text: 'Home', icon: <DashboardIcon />, path: '/' },
    { text: 'Tags', icon: <LabelIcon />, path: '/tags' },
    { text: 'Pipelines', icon: <TimelineIcon />, path: '/pipelines' },
    { text: 'Execution Status', icon: <HistoryIcon />, path: '/execution-status' },
    { text: 'Review Queue', icon: <QueuePlayNextIcon />, path: '/review-queue' },
];

function Sidebar() {
    const [open, setOpen] = useState(false);
    const queryClient = useQueryClient();

    const toggleDrawer = () => {
        setOpen(!open);
    };

    return (
        <Drawer
            variant="permanent"
            sx={{
                width: open ? 240 : 60,
                flexShrink: 0,
                '& .MuiDrawer-paper': {
                    width: open ? 240 : 60,
                    boxSizing: 'border-box',
                    transition: 'width 0.3s',
                    top: 64,
                    height: 'calc(100% - 64px)',
                    display: 'flex',
                    flexDirection: 'column',
                },
            }}
        >
            <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                <IconButton onClick={toggleDrawer} sx={{ alignSelf: 'flex-end', m: 1 }}>
                    <MenuIcon />
                </IconButton>
                <List sx={{ flexGrow: 1 }}>
                    {menuItems.map((item) => (
                        <ListItem
                            key={item.text}
                            component={Link}
                            to={item.path}
                            onClick={() => {
                                if (item.path !== '/tags') {
                                    queryClient.invalidateQueries({ queryKey: ['tags'] });
                                }
                            }}
                        >
                            <ListItemIcon>{item.icon}</ListItemIcon>
                            {open && <ListItemText primary={item.text} />}
                        </ListItem>
                    ))}
                </List>
                <List>
                    <ListItemButton component={Link} to="/settings">
                        <ListItemIcon><SettingsIcon /></ListItemIcon>
                        {open && <ListItemText primary="Settings" />}
                    </ListItemButton>
                    <ListItemButton component={Link} to="/profile">
                        <ListItemIcon><AccountCircleIcon /></ListItemIcon>
                        {open && <ListItemText primary="User Profile" />}
                    </ListItemButton>
                </List>
            </Box>
        </Drawer>
    );
}

export default Sidebar;
