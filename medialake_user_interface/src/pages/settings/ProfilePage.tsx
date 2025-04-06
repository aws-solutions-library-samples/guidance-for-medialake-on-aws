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
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    SelectChangeEvent,
    Stack,
} from '@mui/material';
import {
    Email as EmailIcon,
    Person as PersonIcon,
    Language as LanguageIcon,
} from '@mui/icons-material';
import { useGetUser } from '../../api/hooks/useUsers';
import { getCurrentUser } from 'aws-amplify/auth';
import { useEffect, useState } from 'react';
import { UserAttributes } from '../../api/types/api.types';
import { useTranslation } from 'react-i18next';

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
    const { t, i18n } = useTranslation();
    const [userId, setUserId] = useState<string | null>(null);

    // Load saved language preference when component mounts
    useEffect(() => {
        // Try to get the language from localStorage with different possible keys
        const savedLanguage =
            localStorage.getItem('userLanguage') ||
            localStorage.getItem('i18nextLng') ||
            localStorage.getItem('i18next');
            
        if (savedLanguage) {
            console.log('Loading saved language:', savedLanguage);
            i18n.changeLanguage(savedLanguage);
        }
    }, [i18n]);

    useEffect(() => {
        const getCurrentAuthUser = async () => {
            try {
                const { username } = await getCurrentUser();
                setUserId(username);
            } catch (error) {
                console.error(t('translation.errors.loadFailed', 'Error getting current user:'), error);
            }
        };
        getCurrentAuthUser();
    }, [t]);

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
                <Typography color="error">{t('translation.errors.loadFailed', 'Error loading profile')}: {error.message}</Typography>
            </Box>
        );
    }

    if (!userProfile) {
        return (
            <Box>
                <Typography>{t('common.error', 'No profile data available')}</Typography>
            </Box>
        );
    }

    const unavailable = t('common.error', 'Unavailable');
    const email = userProfile.data?.attributes?.email || unavailable;
    const firstName = userProfile.data?.attributes?.given_name || unavailable;
    const lastName = userProfile.data?.attributes?.family_name || unavailable;
    const username = userProfile.data?.username || unavailable;
    const userStatus = userProfile.data?.user_status || unavailable;

    return (
        <Box>
            <Box sx={{ mb: 4 }}>
                <Typography variant="h4" sx={{
                    fontWeight: 700,
                    mb: 1,
                    color: theme.palette.primary.main,
                }}>
                    {t('profile.title', 'Profile')}
                </Typography>
                <Typography variant="body1" color="text.secondary">
                    {t('profile.description', 'Manage your account settings and preferences')}
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
                            {email !== unavailable ? email[0].toUpperCase() : 'U'}
                        </Avatar>
                        <Typography variant="h5" gutterBottom>
                            {`${firstName} ${lastName}`}
                        </Typography>
                        <Typography variant="body2" color="text.secondary" gutterBottom>
                            {email}
                        </Typography>
                        <Chip
                            label={userStatus}
                            color="success"
                            size="small"
                            sx={{ mt: 1 }}
                        />
                    </Paper>
                </Grid>

                {/* Profile Details */}
                <Grid item xs={12} md={8}>
                    <Paper sx={{ p: 3 }}>
                        <Typography variant="h6" gutterBottom>
                            {t('profile.title', 'Profile')}
                        </Typography>
                        <List>
                            <ListItem>
                                <ListItemIcon>
                                    <EmailIcon color="primary" />
                                </ListItemIcon>
                                <ListItemText
                                    primary={t('translation.users.form.fields.email.label', 'Email')}
                                    secondary={email}
                                />
                            </ListItem>
                            <ListItem>
                                <ListItemIcon>
                                    <PersonIcon color="primary" />
                                </ListItemIcon>
                                <ListItemText
                                    primary={t('translation.users.form.fields.given_name.label', 'First Name')}
                                    secondary={firstName}
                                />
                            </ListItem>
                            <ListItem>
                                <ListItemIcon>
                                    <PersonIcon color="primary" />
                                </ListItemIcon>
                                <ListItemText
                                    primary={t('translation.users.form.fields.family_name.label', 'Last Name')}
                                    secondary={lastName}
                                />
                            </ListItem>
                            <ListItem>
                                <ListItemIcon>
                                    <LanguageIcon color="primary" />
                                </ListItemIcon>
                                <ListItemText
                                    primary={t('common.language', 'Language')}
                                    secondary={
                                        <FormControl variant="outlined" size="small" sx={{ mt: 1, minWidth: 200 }}>
                                            <Select
                                                value={i18n.language}
                                                onChange={(e: SelectChangeEvent) => {
                                                    const newLanguage = e.target.value;
                                                    console.log('Changing language to:', newLanguage);
                                                    
                                                    // Save language in multiple places to ensure it persists
                                                    localStorage.setItem('userLanguage', newLanguage);
                                                    localStorage.setItem('i18nextLng', newLanguage);
                                                    localStorage.setItem('i18next', newLanguage);
                                                    
                                                    // Force language change
                                                    i18n.changeLanguage(newLanguage);
                                                }}
                                            >
                                                <MenuItem value="en">
                                                    <Stack direction="row" spacing={1} alignItems="center">
                                                        <Box sx={{ width: 24, height: 16, border: '1px solid #ccc', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px' }}>
                                                            GB
                                                        </Box>
                                                        <span>English</span>
                                                    </Stack>
                                                </MenuItem>
                                                <MenuItem value="de">
                                                    <Stack direction="row" spacing={1} alignItems="center">
                                                        <Box sx={{ width: 24, height: 16, border: '1px solid #ccc', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px' }}>
                                                            DE
                                                        </Box>
                                                        <span>Deutsch</span>
                                                    </Stack>
                                                </MenuItem>
                                                <MenuItem value="pt">
                                                    <Stack direction="row" spacing={1} alignItems="center">
                                                        <Box sx={{ width: 24, height: 16, border: '1px solid #ccc', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px' }}>
                                                            PT
                                                        </Box>
                                                        <span>Português</span>
                                                    </Stack>
                                                </MenuItem>
                                                <MenuItem value="fr">
                                                    <Stack direction="row" spacing={1} alignItems="center">
                                                        <Box sx={{ width: 24, height: 16, border: '1px solid #ccc', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px' }}>
                                                            FR
                                                        </Box>
                                                        <span>Français</span>
                                                    </Stack>
                                                </MenuItem>
                                                <MenuItem value="zh">
                                                    <Stack direction="row" spacing={1} alignItems="center">
                                                        <Box sx={{ width: 24, height: 16, border: '1px solid #ccc', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px' }}>
                                                            CN
                                                        </Box>
                                                        <span>中文</span>
                                                    </Stack>
                                                </MenuItem>
                                                <MenuItem value="hi">
                                                    <Stack direction="row" spacing={1} alignItems="center">
                                                        <Box sx={{ width: 24, height: 16, border: '1px solid #ccc', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px' }}>
                                                            IN
                                                        </Box>
                                                        <span>हिन्दी</span>
                                                    </Stack>
                                                </MenuItem>
                                                <MenuItem value="ar">
                                                    <Stack direction="row" spacing={1} alignItems="center">
                                                        <Box sx={{ width: 24, height: 16, border: '1px solid #ccc', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px' }}>
                                                            SA
                                                        </Box>
                                                        <span>العربية</span>
                                                    </Stack>
                                                </MenuItem>
                                                <MenuItem value="he">
                                                    <Stack direction="row" spacing={1} alignItems="center">
                                                        <Box sx={{ width: 24, height: 16, border: '1px solid #ccc', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px' }}>
                                                            IL
                                                        </Box>
                                                        <span>עברית</span>
                                                    </Stack>
                                                </MenuItem>
                                            </Select>
                                        </FormControl>
                                    }
                                />
                            </ListItem>
                        </List>
                    </Paper>
                </Grid>
            </Grid>
        </Box>
    );
};

export default ProfilePage;
