import {
    Box,
    Paper,
    Typography,
    Avatar,
    Grid,
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
} from '@mui/icons-material';
import { useGetUser } from '../../api/hooks/useUsers';
import { getCurrentUser } from 'aws-amplify/auth';
import { useEffect, useState } from 'react';
import { UserAttributes } from '../../api/types/api.types';

interface UserProfileData {
    username: string;
    user_status: string;
    enabled: boolean;
    user_created: string;
    last_modified: string;
    attributes: UserAttributes;
}

interface UserProfileResponse {
    status: string;
    message: string;
    data: UserProfileData;
}

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

    // const email = userProfile.data.attributes?.email || 'Unavailable';
    // const firstName = userProfile.data.attributes?.given_name || 'Unavailable';
    // const lastName = userProfile.data.attributes?.family_name || 'Unavailable';

    return (
        // <Box>
        //     <Box sx={{ mb: 4 }}>
        //         <Typography variant="h4" sx={{
        //             fontWeight: 700,
        //             mb: 1,
        //             color: theme.palette.primary.main,
        //         }}>
        //             Profile
        //         </Typography>
        //         <Typography variant="body1" color="text.secondary">
        //             Manage your account settings and preferences
        //         </Typography>
        //     </Box>

        //     <Grid container spacing={3}>
        //         {/* Profile Overview */}
        //         <Grid xs={12} md={4}>
        //             <Paper sx={{ p: 3, textAlign: 'center' }}>
        //                 <Avatar
        //                     sx={{
        //                         width: 120,
        //                         height: 120,
        //                         margin: '0 auto 16px',
        //                         bgcolor: theme.palette.primary.main,
        //                         fontSize: '3rem',
        //                     }}
        //                 >
        //                     {email !== 'Unavailable' ? email[0].toUpperCase() : 'U'}
        //                 </Avatar>
        //                 <Typography variant="h5" gutterBottom>
        //                     {`${firstName} ${lastName}`}
        //                 </Typography>
        //                 <Typography variant="body2" color="text.secondary" gutterBottom>
        //                     {email}
        //                 </Typography>
        //                 <Chip
        //                     label="Active"
        //                     color="success"
        //                     size="small"
        //                     sx={{ mt: 1 }}
        //                 />
        //             </Paper>
        //         </Grid>

        //         {/* Profile Details */}
        //         <Grid xs={12} md={8}>
        //             <Paper sx={{ p: 3 }}>
        //                 <Typography variant="h6" gutterBottom>
        //                     Profile Information
        //                 </Typography>
        //                 <List>
        //                     <ListItem>
        //                         <ListItemIcon>
        //                             <EmailIcon color="primary" />
        //                         </ListItemIcon>
        //                         <ListItemText
        //                             primary="Email"
        //                             secondary={email}
        //                         />
        //                     </ListItem>
        //                     <ListItem>
        //                         <ListItemIcon>
        //                             <PersonIcon color="primary" />
        //                         </ListItemIcon>
        //                         <ListItemText
        //                             primary="First Name"
        //                             secondary={firstName}
        //                         />
        //                     </ListItem>
        //                     <ListItem>
        //                         <ListItemIcon>
        //                             <PersonIcon color="primary" />
        //                         </ListItemIcon>
        //                         <ListItemText
        //                             primary="Last Name"
        //                             secondary={lastName}
        //                         />
        //                     </ListItem>
        //                 </List>
        //             </Paper>
        //         </Grid>
        //     </Grid>
        <Box>
        </Box>
    );
};

export default ProfilePage;
