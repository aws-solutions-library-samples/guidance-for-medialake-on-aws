import React from 'react';
import {
    Box,
    Paper,
    Typography,
    Grid,
    Avatar,
    Button,
    Divider,
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    useTheme,
    Chip,
} from '@mui/material';
import {
    Email as EmailIcon,
    Phone as PhoneIcon,
    Business as BusinessIcon,
    LocationOn as LocationIcon,
    Schedule as ScheduleIcon,
    Security as SecurityIcon,
    Notifications as NotificationsIcon,
    Language as LanguageIcon,
} from '@mui/icons-material';

const ProfilePage: React.FC = () => {
    const theme = useTheme();

    const userProfile = {
        name: 'Alex Johnson',
        role: 'Senior Media Manager',
        email: 'alex.johnson@medialake.com',
        phone: '+1 (555) 123-4567',
        organization: 'MediaLake Inc.',
        location: 'San Francisco, CA',
        timezone: 'Pacific Time (PT)',
        joinDate: 'January 2023',
        recentActivity: [
            { action: 'Created new pipeline', time: '2 hours ago' },
            { action: 'Updated asset metadata', time: '4 hours ago' },
            { action: 'Reviewed content', time: '1 day ago' },
        ],
        stats: [
            { label: 'Assets Managed', value: '1,234' },
            { label: 'Pipelines Created', value: '45' },
            { label: 'Reviews Completed', value: '328' },
        ],
    };

    return (
        <Box>
            <Box sx={{ mb: 4 }}>
                <Typography variant="h4" sx={{ fontWeight: 600, mb: 1 }}>
                    Profile
                </Typography>
                <Typography variant="body1" color="text.secondary">
                    Manage your account settings and preferences
                </Typography>
            </Box>

            <Grid container spacing={3}>
                {/* Profile Overview */}
                <Grid item xs={12} md={4}>
                    <Paper sx={{ p: 3, textAlign: 'center' }}>
                        <Avatar
                            sx={{
                                width: 120,
                                height: 120,
                                margin: '0 auto 16px',
                                bgcolor: theme.palette.primary.main,
                                fontSize: '3rem',
                            }}
                        >
                            {userProfile.name.charAt(0)}
                        </Avatar>
                        <Typography variant="h5" gutterBottom>
                            {userProfile.name}
                        </Typography>
                        <Typography variant="body2" color="text.secondary" gutterBottom>
                            {userProfile.role}
                        </Typography>
                        <Chip
                            label="Active"
                            color="success"
                            size="small"
                            sx={{ mt: 1 }}
                        />
                        <Button
                            variant="outlined"
                            fullWidth
                            sx={{ mt: 2 }}
                        >
                            Edit Profile
                        </Button>
                    </Paper>

                    {/* Quick Stats */}
                    <Paper sx={{ p: 3, mt: 3 }}>
                        <Typography variant="h6" gutterBottom>
                            Activity Overview
                        </Typography>
                        <Grid container spacing={2}>
                            {userProfile.stats.map((stat) => (
                                <Grid item xs={12} key={stat.label}>
                                    <Box sx={{ textAlign: 'center', p: 1 }}>
                                        <Typography variant="h4" color="primary">
                                            {stat.value}
                                        </Typography>
                                        <Typography variant="body2" color="text.secondary">
                                            {stat.label}
                                        </Typography>
                                    </Box>
                                </Grid>
                            ))}
                        </Grid>
                    </Paper>
                </Grid>

                {/* Profile Details */}
                <Grid item xs={12} md={8}>
                    <Paper sx={{ p: 3, mb: 3 }}>
                        <Typography variant="h6" gutterBottom>
                            Contact Information
                        </Typography>
                        <List>
                            <ListItem>
                                <ListItemIcon>
                                    <EmailIcon color="primary" />
                                </ListItemIcon>
                                <ListItemText
                                    primary="Email"
                                    secondary={userProfile.email}
                                />
                            </ListItem>
                            <ListItem>
                                <ListItemIcon>
                                    <PhoneIcon color="primary" />
                                </ListItemIcon>
                                <ListItemText
                                    primary="Phone"
                                    secondary={userProfile.phone}
                                />
                            </ListItem>
                            <ListItem>
                                <ListItemIcon>
                                    <BusinessIcon color="primary" />
                                </ListItemIcon>
                                <ListItemText
                                    primary="Organization"
                                    secondary={userProfile.organization}
                                />
                            </ListItem>
                            <ListItem>
                                <ListItemIcon>
                                    <LocationIcon color="primary" />
                                </ListItemIcon>
                                <ListItemText
                                    primary="Location"
                                    secondary={userProfile.location}
                                />
                            </ListItem>
                        </List>
                    </Paper>

                    <Paper sx={{ p: 3 }}>
                        <Typography variant="h6" gutterBottom>
                            Recent Activity
                        </Typography>
                        <List>
                            {userProfile.recentActivity.map((activity, index) => (
                                <React.Fragment key={index}>
                                    <ListItem>
                                        <ListItemIcon>
                                            <ScheduleIcon color="action" />
                                        </ListItemIcon>
                                        <ListItemText
                                            primary={activity.action}
                                            secondary={activity.time}
                                        />
                                    </ListItem>
                                    {index < userProfile.recentActivity.length - 1 && <Divider />}
                                </React.Fragment>
                            ))}
                        </List>
                    </Paper>

                    {/* Quick Actions */}
                    <Box sx={{ mt: 3 }}>
                        <Grid container spacing={2}>
                            <Grid item xs={12} sm={4}>
                                <Button
                                    variant="outlined"
                                    fullWidth
                                    startIcon={<SecurityIcon />}
                                >
                                    Security Settings
                                </Button>
                            </Grid>
                            <Grid item xs={12} sm={4}>
                                <Button
                                    variant="outlined"
                                    fullWidth
                                    startIcon={<NotificationsIcon />}
                                >
                                    Notification Preferences
                                </Button>
                            </Grid>
                            <Grid item xs={12} sm={4}>
                                <Button
                                    variant="outlined"
                                    fullWidth
                                    startIcon={<LanguageIcon />}
                                >
                                    Language & Region
                                </Button>
                            </Grid>
                        </Grid>
                    </Box>
                </Grid>
            </Grid>
        </Box>
    );
};

export default ProfilePage;
