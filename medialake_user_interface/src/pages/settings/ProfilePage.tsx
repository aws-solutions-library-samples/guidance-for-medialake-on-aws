import React from 'react';
import {
    Box,
    Paper,
    Typography,
    Grid,
    Avatar,
    Button,
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    useTheme,
    Chip,
    CircularProgress,
} from '@mui/material';
import {
    Email as EmailIcon,
    Person as PersonIcon,
    Security as SecurityIcon,
    Notifications as NotificationsIcon,
    Language as LanguageIcon,
} from '@mui/icons-material';
import { useGetUser } from '../../api/hooks/useUsers';
import { getCurrentUser } from 'aws-amplify/auth';
import { useEffect, useState } from 'react';

const ProfilePage: React.FC = () => {
    const theme = useTheme();
    const [userId, setUserId] = useState<string | null>(null);

    useEffect(() => {
        const getCurrentAuthUser = async () => {
            try {
                const { username } = await getCurrentUser();
                setUserId(username);
            } catch (error) {
                console.error('Error getting current user:', error);
            }
        };
        getCurrentAuthUser();
    }, []);

    const { data: userProfile, isLoading, error } = useGetUser(userId || '');

    if (isLoading) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
                <CircularProgress />
            </Box>
        );
    }

    if (error) {
        return (
            <Box>
                <Typography color="error">Error loading profile: {error.message}</Typography>
            </Box>
        );
    }

    if (!userProfile) {
        return (
            <Box>
                <Typography>No profile data available</Typography>
            </Box>
        );
    }

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
                            {userProfile.data.given_name?.[0] || userProfile.data.username?.[0]}
                        </Avatar>
                        <Typography variant="h5" gutterBottom>
                            {`${userProfile.data.given_name || ''} ${userProfile.data.family_name || ''}`}
                        </Typography>
                        <Typography variant="body2" color="text.secondary" gutterBottom>
                            {userProfile.data.username}
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
                </Grid>

                {/* Profile Details */}
                <Grid item xs={12} md={8}>
                    <Paper sx={{ p: 3, mb: 3 }}>
                        <Typography variant="h6" gutterBottom>
                            Profile Information
                        </Typography>
                        <List>
                            <ListItem>
                                <ListItemIcon>
                                    <PersonIcon color="primary" />
                                </ListItemIcon>
                                <ListItemText
                                    primary="Username"
                                    secondary={userProfile.data.username}
                                />
                            </ListItem>
                            <ListItem>
                                <ListItemIcon>
                                    <EmailIcon color="primary" />
                                </ListItemIcon>
                                <ListItemText
                                    primary="Email"
                                    secondary={userProfile.data.email}
                                />
                            </ListItem>
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
