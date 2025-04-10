import React, { Suspense } from 'react';
import { ErrorBoundary } from 'react-error-boundary';
import { RouterProvider } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import queryClient from '../api/queryClient';
import { AwsConfigProvider } from '../common/hooks/aws-config-context';
import { AuthProvider } from '../common/hooks/auth-context';
import '@aws-amplify/ui-react/styles.css';
import { ModalProvider } from './common/ModalConnector';
import { ThemeProvider } from '../hooks/useTheme';
import { ThemeWrapper } from './ThemeWrapper';
import { TimezoneProvider } from '../contexts/TimezoneContext';
import { TableDensityProvider } from '../contexts/TableDensityContext';
import { DirectionProvider } from '../contexts/DirectionContext';
import { router } from '../routes/router';
import { Box, CircularProgress } from '@mui/material';

const LoadingFallback = () => (
    <Box sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh'
    }}>
        <CircularProgress />
    </Box>
);

const ErrorFallback = ({ error }: { error: Error }) => (
    <Box sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        flexDirection: 'column',
        gap: 2
    }}>
        <h2>Something went wrong:</h2>
        <pre style={{ color: 'red' }}>{error.message}</pre>
    </Box>
);

const AppConfigured = () => {
    return (
        <ErrorBoundary FallbackComponent={ErrorFallback}>
            <Suspense fallback={<LoadingFallback />}>
                <QueryClientProvider client={queryClient}>
                    <AwsConfigProvider>
                        <AuthProvider>
                            <TimezoneProvider>
                                <ThemeProvider>
                                    <DirectionProvider>
                                        <TableDensityProvider>
                                            <ThemeWrapper>
                                                <ModalProvider>
                                                    <RouterProvider router={router} />
                                                    </ModalProvider>
                                                </ThemeWrapper>
                                            </TableDensityProvider>
                                        </DirectionProvider>
                                    </ThemeProvider>
                                </TimezoneProvider>
                        </AuthProvider>
                    </AwsConfigProvider>
                </QueryClientProvider>
            </Suspense>
        </ErrorBoundary>
    );
};

export default AppConfigured;