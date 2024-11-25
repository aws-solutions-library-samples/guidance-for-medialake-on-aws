import React, { Suspense } from 'react';
import { Box, Stack, Typography, Paper, useTheme, useMediaQuery, CircularProgress, Grid } from '@mui/material';
import { Statistics } from '../features/home/Statistics';
import { Collections } from '../features/home/Collections';
import { SmartFolders } from '../features/home/SmartFolders';
import { ConnectedStorage } from '../features/home/ConnectedStorage';
import { SharedCollections } from '../features/home/SharedCollections';
import { Favorites } from '../features/home/Favorites';
import { ErrorBoundary } from 'react-error-boundary';
import { useTranslation } from 'react-i18next';

const LoadingFallback = () => {
    const { t } = useTranslation();
    return (
        <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '200px' }}>
            <CircularProgress />
        </Box>
    );
};

const ErrorFallback = ({ error }: { error: Error }) => {
    const { t } = useTranslation();
    return (
        <Box sx={{ p: 3, color: 'error.main' }}>
            <Typography variant="h6">{t('common.error')}:</Typography>
            <Typography variant="body1">{error.message}</Typography>
        </Box>
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
                top: 64, // Header height
                left: 240, // Sidebar width
                right: 0,
                bottom: 0,
                bgcolor: '#f6f8fc',
                overflowY: 'auto',
                overflowX: 'hidden',
            }}
        >
            <Box sx={{ p: { xs: 2, sm: 3 } }}>
                <Box sx={{ mb: 4 }}>
                    <Typography
                        variant="h4"
                        component="h1"
                        sx={{
                            fontWeight: 600,
                            color: 'primary.main',
                            mb: 1
                        }}
                    >
                        {t('home.welcome')}
                    </Typography>
                    <Typography
                        variant="subtitle1"
                        color="text.secondary"
                    >
                        {t('home.description')}
                    </Typography>
                </Box>

                <Stack spacing={3}>
                    <ErrorBoundary FallbackComponent={ErrorFallback}>
                        <Suspense fallback={<LoadingFallback />}>
                            <Statistics />
                        </Suspense>
                    </ErrorBoundary>

                    <Paper
                        elevation={0}
                        sx={{
                            p: 3,
                            borderRadius: 2,
                            backgroundColor: 'rgba(255, 255, 255, 0.8)',
                            backdropFilter: 'blur(10px)',
                            border: '1px solid',
                            borderColor: 'divider'
                        }}
                    >
                        <ErrorBoundary FallbackComponent={ErrorFallback}>
                            <Suspense fallback={<LoadingFallback />}>
                                <Collections />
                            </Suspense>
                        </ErrorBoundary>
                    </Paper>

                    <Paper
                        elevation={0}
                        sx={{
                            p: 3,
                            borderRadius: 2,
                            backgroundColor: 'rgba(255, 255, 255, 0.8)',
                            backdropFilter: 'blur(10px)',
                            border: '1px solid',
                            borderColor: 'divider'
                        }}
                    >
                        <ErrorBoundary FallbackComponent={ErrorFallback}>
                            <Suspense fallback={<LoadingFallback />}>
                                <SharedCollections />
                            </Suspense>
                        </ErrorBoundary>
                    </Paper>

                    <Paper
                        elevation={0}
                        sx={{
                            p: 3,
                            borderRadius: 2,
                            backgroundColor: 'rgba(255, 255, 255, 0.8)',
                            backdropFilter: 'blur(10px)',
                            border: '1px solid',
                            borderColor: 'divider'
                        }}
                    >
                        <ErrorBoundary FallbackComponent={ErrorFallback}>
                            <Suspense fallback={<LoadingFallback />}>
                                <Favorites />
                            </Suspense>
                        </ErrorBoundary>
                    </Paper>

                    <Grid container spacing={3}>
                        <Grid item xs={12} md={6}>
                            <Paper
                                elevation={0}
                                sx={{
                                    p: 3,
                                    height: '100%',
                                    borderRadius: 2,
                                    backgroundColor: 'rgba(255, 255, 255, 0.8)',
                                    backdropFilter: 'blur(10px)',
                                    border: '1px solid',
                                    borderColor: 'divider'
                                }}
                            >
                                <ErrorBoundary FallbackComponent={ErrorFallback}>
                                    <Suspense fallback={<LoadingFallback />}>
                                        <SmartFolders />
                                    </Suspense>
                                </ErrorBoundary>
                            </Paper>
                        </Grid>
                        <Grid item xs={12} md={6}>
                            <Paper
                                elevation={0}
                                sx={{
                                    p: 3,
                                    height: '100%',
                                    borderRadius: 2,
                                    backgroundColor: 'rgba(255, 255, 255, 0.8)',
                                    backdropFilter: 'blur(10px)',
                                    border: '1px solid',
                                    borderColor: 'divider'
                                }}
                            >
                                <ErrorBoundary FallbackComponent={ErrorFallback}>
                                    <Suspense fallback={<LoadingFallback />}>
                                        <ConnectedStorage />
                                    </Suspense>
                                </ErrorBoundary>
                            </Paper>
                        </Grid>
                    </Grid>
                </Stack>
            </Box>
        </Box>
    );
};

export default Home;
