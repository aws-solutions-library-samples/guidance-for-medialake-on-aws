import React from 'react';
import { Box, Grid, Typography, Paper, useTheme, useMediaQuery } from '@mui/material';
import { useTranslation } from 'react-i18next';
import FavoriteIcon from '@mui/icons-material/Favorite';
import CollectionsIcon from '@mui/icons-material/Collections';
import ShareIcon from '@mui/icons-material/Share';

const FeatureCard: React.FC<{
    title: string;
    icon: React.ReactNode;
}> = ({ title, icon }) => {
    const { t } = useTranslation();
    return (
        <Paper
            elevation={0}
            sx={{
                p: 3,
                height: '100%',
                borderRadius: 2,
                backgroundColor: 'background.paper',
                border: '1px solid',
                borderColor: 'divider',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                textAlign: 'center',
                transition: 'transform 0.2s ease-in-out',
                '&:hover': {
                    transform: 'translateY(-4px)',
                }
            }}
        >
            <Box sx={{
                color: 'primary.main',
                mb: 2,
                '& svg': {
                    fontSize: 48
                }
            }}>
                {icon}
            </Box>
            <Typography variant="h6" gutterBottom>
                {title}
            </Typography>
            <Typography
                variant="body2"
                color="text.secondary"
                sx={{ mt: 1 }}
            >
                {t('translation.home.comingSoon')}
            </Typography>
        </Paper>
    );
};

const Home: React.FC = () => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const { t } = useTranslation();

    return (
        <Box
            component="main"
            sx={{
                position: 'fixed',
                top: 64,
                left: 240,
                right: 0,
                bottom: 0,
                bgcolor: 'background.default',
                overflowY: 'auto',
                overflowX: 'hidden',
            }}
        >
            <Box sx={{ p: { xs: 2, sm: 3 } }}>
                <Box sx={{
                    mb: 6,
                    textAlign: 'center',
                    maxWidth: 800,
                    mx: 'auto'
                }}>
                    <Typography
                        variant="h3"
                        component="h1"
                        sx={{
                            fontWeight: 700,
                            color: 'primary.main',
                            mb: 2
                        }}
                    >
                        {t('app.branding.name')}
                    </Typography>
                    <Typography
                        variant="h5"
                        color="text.secondary"
                        sx={{ mb: 4 }}
                    >
                        {t('translation.home.description')}
                    </Typography>
                </Box>

                <Grid container spacing={4} sx={{ maxWidth: 1200, mx: 'auto' }}>
                    <Grid item xs={12} md={4}>
                        <FeatureCard
                            title={t('translation.home.favorites')}
                            icon={<FavoriteIcon />}
                        />
                    </Grid>
                    <Grid item xs={12} md={4}>
                        <FeatureCard
                            title={t('translation.home.collections')}
                            icon={<CollectionsIcon />}
                        />
                    </Grid>
                    <Grid item xs={12} md={4}>
                        <FeatureCard
                            title={t('translation.home.sharing')}
                            icon={<ShareIcon />}
                        />
                    </Grid>
                </Grid>

            </Box>
        </Box>
    );
};

export default Home;
