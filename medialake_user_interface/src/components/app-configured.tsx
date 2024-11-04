import React, { Suspense, useEffect } from 'react';
import { ErrorBoundary } from 'react-error-boundary';
import { RouterProvider, createBrowserRouter, Outlet, Navigate, useNavigate } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import queryClient from '../queryClient';
import { AwsConfigProvider } from '../common/hooks/aws-config-context';
import { AuthProvider, useAuth } from '../common/hooks/auth-context';
import { Box, CircularProgress } from '@mui/material';
import TopBar from '../TopBar';
import Sidebar from '../Sidebar';
import { S3Explorer } from './home/S3Explorer';
import { ConnectedStorage } from './home/ConnectedStorage';
import SettingsComponent from '../SettingsComponent';
import ExecutionStatusPage from '../ExecutionStatusPage';
import PipelinesPage from '../PipelinesPage';
import ReviewQueue from '../reviewQueue';
import TagsPage from '../TagsPage';
import { Authenticator } from '@aws-amplify/ui-react';
import { fetchAuthSession, signIn } from 'aws-amplify/auth';
import { StorageHelper } from '../common/helpers/storage-helper';
import '@aws-amplify/ui-react/styles.css';
import SearchResults from './SearchResults';

// Protected Route Component
const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
    const { isAuthenticated } = useAuth();
    const navigate = useNavigate();

    useEffect(() => {
        if (!isAuthenticated) {
            navigate('/auth');
        }
    }, [isAuthenticated, navigate]);

    return isAuthenticated ? <>{children}</> : null;
};

const AppLayout = () => {
    return (
        <Box sx={{ display: 'flex' }}>
            <TopBar />
            <Sidebar />
            <Box component="main" sx={{ flexGrow: 1, p: 3, mt: 8 }}>
                <Outlet />
            </Box>
        </Box>
    );
};

const AuthPage = () => {
    const { setIsAuthenticated } = useAuth();
    const navigate = useNavigate();

    return (
        <Box sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            minHeight: '100vh',
            bgcolor: 'background.default'
        }}>
            <Authenticator
                loginMechanisms={['email']}
                signUpAttributes={['email']}
                hideSignUp={true}
                services={{
                    async handleSignIn(input) {
                        try {
                            // First sign in using the provided credentials
                            const signInResult = await signIn(input);

                            // Then fetch the session to get the token
                            const session = await fetchAuthSession();
                            const token = session.tokens?.idToken?.toString();

                            if (token) {
                                StorageHelper.setToken(token);
                                setIsAuthenticated(true);
                                navigate('/');
                            }

                            return {
                                isSignedIn: true,
                                nextStep: {
                                    signInStep: 'DONE'
                                }
                            };
                        } catch (error) {
                            console.error('Error during sign in:', error);
                            throw error;
                        }
                    }
                }}
            />
        </Box>
    );
};

// Wrapper component for SearchResults that provides the onImageSelect handler
const SearchResultsWrapper = () => {
    const handleImageSelect = (image: any) => {
        console.log('Selected image:', image);
        // Add any additional image selection handling logic here
    };

    return <SearchResults onImageSelect={handleImageSelect} />;
};

const router = createBrowserRouter([
    {
        path: '/auth',
        element: <AuthPage />
    },
    {
        path: '/',
        element: (
            <ProtectedRoute>
                <AppLayout />
            </ProtectedRoute>
        ),
        children: [
            {
                index: true,
                element: <ConnectedStorage />
            },
            {
                path: 's3/explorer/:connectorId',
                element: <S3Explorer />
            },
            {
                path: 'settings',
                element: <SettingsComponent />
            },
            {
                path: 'execution-status',
                element: <ExecutionStatusPage />
            },
            {
                path: 'executions/:executionId',
                element: <ExecutionStatusPage />
            },
            {
                path: 'review-queue',
                element: <ReviewQueue />
            },
            {
                path: 'pipelines',
                element: <PipelinesPage />
            },
            {
                path: 'tags',
                element: <TagsPage />
            },
            {
                path: 'search',
                element: <SearchResultsWrapper />
            }
        ]
    }
]);

const LoadingFallback = () => (
    <Box
        sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100vh'
        }}
    >
        <CircularProgress />
    </Box>
);

const ErrorFallback = ({ error }: { error: Error }) => (
    <Box
        sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            height: '100vh',
            flexDirection: 'column',
            gap: 2
        }}
    >
        <h2>Something went wrong:</h2>
        <pre style={{ color: 'red' }}>{error.message}</pre>
    </Box>
);

const AppConfigured: React.FC = () => {
    return (
        <ErrorBoundary FallbackComponent={ErrorFallback}>
            <Suspense fallback={<LoadingFallback />}>
                <QueryClientProvider client={queryClient}>
                    <AwsConfigProvider>
                        <AuthProvider>
                            <RouterProvider router={router} />
                        </AuthProvider>
                    </AwsConfigProvider>
                </QueryClientProvider>
            </Suspense>
        </ErrorBoundary>
    );
};

export default AppConfigured;
