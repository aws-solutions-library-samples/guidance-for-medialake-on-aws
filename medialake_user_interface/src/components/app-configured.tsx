import React, { Suspense, useEffect, useState } from 'react';
import { SidebarContext } from '../contexts/SidebarContext';
import { ErrorBoundary } from 'react-error-boundary';
import { RouterProvider, createBrowserRouter, Outlet, Navigate, useNavigate, useParams } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import queryClient from '../api/queryClient';
import { AwsConfigProvider } from '../common/hooks/aws-config-context';
import { AuthProvider, useAuth } from '../common/hooks/auth-context';
import { Authenticator, ThemeProvider as AmplifyThemeProvider, Theme } from '@aws-amplify/ui-react';
import { fetchAuthSession, signIn, confirmSignIn } from 'aws-amplify/auth';
import { Box, CircularProgress } from '@mui/material';
import TopBar from '../TopBar';
import Sidebar from '../Sidebar';
import SearchPage from '../pages/SearchPage';
import AssetsPage from '../pages/AssetsPage';
import { S3Explorer } from '../features/home/S3Explorer';
import Home from '../pages/Home';
import SettingsComponent from '../features/settings/SettingsLayout';
import ExecutionsPage from '../pages/ExecutionsPage';
import PipelinesPage from '../pages/PipelinesPage';
import { StorageHelper } from '../common/helpers/storage-helper';
import '@aws-amplify/ui-react/styles.css';
import ImageDetailPage from '../pages/ImageDetailPage';
import { ModalProvider } from '../components/common/ModalConnector';
import { ThemeProvider } from '../hooks/useTheme';
import { ThemeWrapper } from '../components/ThemeWrapper';
import { TimezoneProvider } from '../contexts/TimezoneContext';
import { TableDensityProvider } from '../contexts/TableDensityContext';

const theme: Theme = {
    name: 'mediaLakeTheme',
    tokens: {
        colors: {
            background: {
                primary: 'transparent',
                secondary: 'transparent',
            },
            brand: {
                primary: {
                    10: '#ffffff',
                    20: '#ffffff',
                    40: '#ffffff',
                    60: '#ffffff',
                    80: '#e6f7ff',
                    90: '#bae7ff',
                    100: '#91d5ff',
                },
            },
            font: {
                interactive: '#ffffff',
            },
            border: {
                primary: 'rgba(255, 255, 255, 0.3)',
                secondary: 'rgba(255, 255, 255, 0.2)',
            },
        },
        components: {
            authenticator: {
                router: {
                    borderWidth: '0',
                    boxShadow: 'none',
                    backgroundColor: 'transparent',
                },
            },
            button: {
                primary: {
                    backgroundColor: 'rgba(255, 255, 255, 0.2)',
                    _hover: {
                        backgroundColor: 'rgba(255, 255, 255, 0.3)',
                    },
                    _active: {
                        backgroundColor: 'rgba(255, 255, 255, 0.4)',
                    },
                    _focus: {
                        backgroundColor: 'rgba(255, 255, 255, 0.3)',
                    },
                },
            },
        },
        fonts: {
            default: {
                variable: 'Inter, -apple-system, system-ui, sans-serif',
                static: 'Inter, -apple-system, system-ui, sans-serif',
            },
        },
    },
};

// Custom UI components for Auth
const components = {
    Header() {
        return (
            <Box
                style={{
                    textAlign: 'center',
                    padding: '2rem 2.5rem',
                    color: 'white',
                }}
            >
                <img
                    src="/logo.png"
                    alt="MediaLake Logo"
                    style={{
                        height: '40px',
                        marginBottom: '1rem',
                    }}
                />
                <h1
                    style={{
                        fontSize: '1.5rem',
                        fontWeight: '600',
                        margin: 0,
                        color: 'white',
                    }}
                >
                    Welcome to MediaLake
                </h1>
                <p
                    style={{
                        fontSize: '0.875rem',
                        color: 'rgba(255, 255, 255, 0.85)',
                        margin: '0.5rem 0 0',
                    }}
                >
                    A data lake for your media, metadata, and media pipelines.
                </p>
            </Box>
        );
    },
    Footer() {
        return null;
    },
};

const AuthPage = () => {
    const { setIsAuthenticated, isAuthenticated } = useAuth();
    const navigate = useNavigate();

    useEffect(() => {
        if (isAuthenticated) {
            navigate('/');
        }
    }, [isAuthenticated, navigate]);

    return (
        <Box sx={{
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            minHeight: '100vh',
            bgcolor: '#f0f2f5',
            backgroundImage: 'linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)',
            padding: '20px',
            '& .amplify-authenticator': {
                maxWidth: '400px',
                width: '100%',
                marginBottom: '1rem',
            },
            '& [data-amplify-authenticator]': {
                background: 'linear-gradient(135deg, #0050b3 0%, #002766 100%)',
                borderRadius: '8px',
                boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
                overflow: 'hidden',
            },
            '& [data-amplify-container]': {
                padding: '0',
            },
            '& [data-amplify-form]': {
                padding: '0 2rem 2rem',
            },
            '& .amplify-button': {
                backgroundColor: 'rgba(255, 255, 255, 0.2)',
                color: 'white',
                '&:hover': {
                    backgroundColor: 'rgba(255, 255, 255, 0.3)',
                },
            },
            '& .amplify-field': {
                '--amplify-components-field-label-color': 'rgba(255, 255, 255, 0.9)',
            },
            '& .amplify-input': {
                backgroundColor: 'rgba(255, 255, 255, 0.1)',
                color: 'white',
                borderColor: 'rgba(255, 255, 255, 0.2)',
                '&:focus': {
                    borderColor: 'rgba(255, 255, 255, 0.5)',
                    backgroundColor: 'rgba(255, 255, 255, 0.15)',
                },
                '&::placeholder': {
                    color: 'rgba(255, 255, 255, 0.5)',
                },
            },
            '& .amplify-text': {
                color: 'rgba(255, 255, 255, 0.9)',
            },
            '& .amplify-label': {
                color: 'rgba(255, 255, 255, 0.9)',
            },
            '& .amplify-heading': {
                color: 'rgba(255, 255, 255, 0.9)',
            },
            '& [data-amplify-footer] .amplify-text': {
                color: 'white',
            },
            '& a': {
                color: 'rgba(255, 255, 255, 0.9)',
                '&:hover': {
                    color: 'white',
                },
            },
        }}>
            <AmplifyThemeProvider theme={theme}>
                <Authenticator
                    loginMechanisms={['email']}
                    signUpAttributes={['email']}
                    hideSignUp={true}
                    components={components}
                    services={{
                        async handleSignIn(input) {
                            try {
                                const signInResult = await signIn(input);

                                if (signInResult.nextStep.signInStep === 'CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED') {
                                    return {
                                        isSignedIn: false,
                                        nextStep: {
                                            signInStep: 'CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED'
                                        }
                                    };
                                }

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
                        },
                        async handleConfirmSignIn(input) {
                            try {
                                const confirmResult = await confirmSignIn(input);

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
                                console.error('Error during confirm sign in:', error);
                                throw error;
                            }
                        }
                    }}
                />
            </AmplifyThemeProvider>
        </Box>
    );
};

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
    const { isAuthenticated } = useAuth();

    return isAuthenticated ? <>{children}</> : <Navigate to="/sign-in" replace />;
};

const AppLayout = () => {
    const [isCollapsed, setIsCollapsed] = useState(false);

    return (
        <SidebarContext.Provider value={{ isCollapsed, setIsCollapsed }}>
            <Box sx={{ display: 'flex' }}>
                <TopBar />
                <Sidebar />
                <Box component="main" sx={{
                    flexGrow: 1,
                    mt: 8,
                    display: 'flex',
                    flexDirection: 'column',
                    minWidth: 0, // Important for proper flex behavior
                    height: 'calc(100vh - 64px)', // 64px is the TopBar height
                    overflow: 'hidden'
                }}>
                    <Outlet />
                </Box>
            </Box>
        </SidebarContext.Provider>
    );
};

const S3ExplorerWrapper = () => {
    const { connectorId } = useParams<{ connectorId: string }>();
    return <S3Explorer connectorId={connectorId!} />;
};

const router = createBrowserRouter([
    {
        path: '/sign-in',
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
                element: <Home />
            },
            {
                path: 'search',
                element: <SearchPage />
            },
            {
                path: 's3/explorer/:connectorId',
                element: <S3ExplorerWrapper />
            },
            {
                path: 'settings/*',
                element: <SettingsComponent />
            },
            {
                path: 'assets',
                element: <AssetsPage />
            },
            {
                path: 'executions',
                element: <ExecutionsPage />
            },
            {
                path: 'pipelines',
                element: <PipelinesPage />
            },
            {
                path: 'images/:id',
                element: <ImageDetailPage />
            },
            {
                path: '*',
                element: <Navigate to="/" replace />
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
                            <TimezoneProvider>
                                <ThemeProvider>
                                    <TableDensityProvider>
                                        <ThemeWrapper>
                                            <ModalProvider>
                                                <RouterProvider router={router} />
                                            </ModalProvider>
                                        </ThemeWrapper>
                                    </TableDensityProvider>
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
