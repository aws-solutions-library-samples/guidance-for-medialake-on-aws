import React, { useState } from 'react';
import { Drawer, List, ListItem, ListItemIcon, ListItemText, IconButton, Box } from '@mui/material';
import { Home as HomeIcon, Menu as MenuIcon, AccountCircle as AccountCircleIcon, Settings as SettingsIcon } from '@mui/icons-material';
import { Link } from 'react-router-dom';
import { Tag as TagIcon } from '@mui/icons-material';
import SettingsEthernetIcon from '@mui/icons-material/SettingsEthernet';
import AssessmentIcon from '@mui/icons-material/Assessment';
import QueuePlayNextIcon from '@mui/icons-material/QueuePlayNext'; // New import for Review Queue icon
import SearchIcon from '@mui/icons-material/Search'; // New import for Search icon
import DashboardIcon from '@mui/icons-material/Dashboard'; // New import for Home icon
import LabelIcon from '@mui/icons-material/Label'; // New import for Tags icon
import TimelineIcon from '@mui/icons-material/Timeline'; // New import for Pipelines icon
import HistoryIcon from '@mui/icons-material/History'; // New import for Execution Status icon

const menuItems = [
    { text: 'Search', icon: <SearchIcon />, path: '/search' },
    { text: 'Home', icon: <DashboardIcon />, path: '/' },
    { text: 'Tags', icon: <LabelIcon />, path: '/tags' },
    { text: 'Pipelines', icon: <TimelineIcon />, path: '/pipelines' },
    { text: 'Execution Status', icon: <HistoryIcon />, path: '/execution-status' },
    { text: 'Review Queue', icon: <QueuePlayNextIcon />, path: '/review-queue' }, // New menu item
];

function Sidebar() {
    const [open, setOpen] = useState(false);

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
                        <ListItem button key={item.text} component={Link} to={item.path}>
                            <ListItemIcon>{item.icon}</ListItemIcon>
                            {open && <ListItemText primary={item.text} />}
                        </ListItem>
                    ))}
                </List>
                <List>
                    <ListItem button component={Link} to="/settings">
                        <ListItemIcon><SettingsIcon /></ListItemIcon>
                        {open && <ListItemText primary="Settings" />}
                    </ListItem>
                    <ListItem button component={Link} to="/profile">
                        <ListItemIcon><AccountCircleIcon /></ListItemIcon>
                        {open && <ListItemText primary="User Profile" />}
                    </ListItem>
                </List>
            </Box>
        </Drawer>
    );
}

export default Sidebar;
