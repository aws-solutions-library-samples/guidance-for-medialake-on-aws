import React, { Suspense, useEffect, useState } from 'react';
import { SidebarContext } from '../contexts/SidebarContext';
import { ErrorBoundary } from 'react-error-boundary';
import { RouterProvider, createBrowserRouter, Outlet, Navigate, useNavigate, useParams } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import queryClient from '../api/queryClient';
import { AwsConfigProvider, useAwsConfig } from '../common/hooks/aws-config-context';
import { AuthProvider, useAuth } from '../common/hooks/auth-context';
import { Authenticator, ThemeProvider as AmplifyThemeProvider, Theme } from '@aws-amplify/ui-react';
import { fetchAuthSession, signIn, confirmSignIn, signInWithRedirect } from 'aws-amplify/auth';
import { Box, CircularProgress, Button, Typography, Stack, Divider } from '@mui/material';
import TopBar from '../TopBar';
import Sidebar from '../Sidebar';
import SearchPage from '../pages/SearchPage';
import AssetsPage from '../pages/AssetsPage';
import { S3Explorer } from '../features/home/S3Explorer';
import Home from '../pages/Home';
import SettingsComponent from '../features/settings/SettingsLayout';
import ExecutionsPage from '../pages/ExecutionsPage';
import { PipelinesPage, PipelineEditorPage } from '@/features/pipelines/pages';
import { StorageHelper } from '../common/helpers/storage-helper';
import '@aws-amplify/ui-react/styles.css';
import ImageDetailPage from '../pages/ImageDetailPage';
import { ModalProvider } from '../components/common/ModalConnector';
import { ThemeProvider } from '../hooks/useTheme';
import { ThemeWrapper } from '../components/ThemeWrapper';
import { TimezoneProvider } from '../contexts/TimezoneContext';
import { TableDensityProvider } from '../contexts/TableDensityContext';
import VideoDetailPage from '@/pages/VideoDetailPage';

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

const components = {
    Header() {
        return null;
    },
    Footer() {
        return null;
    },
    SignIn: {
        Header() {
            return null;
        },
        Footer() {
            return null;
        }
    }
};

const AuthPage = () => {
    const { setIsAuthenticated, isAuthenticated } = useAuth();
    const navigate = useNavigate();
    const awsConfig = useAwsConfig();

    useEffect(() => {
        if (isAuthenticated) {
            navigate('/');
        }
    }, [isAuthenticated, navigate]);

    if (!awsConfig) {
        return <CircularProgress />;
    }

    const hasSamlProvider = awsConfig.Auth.identity_providers.some(
        provider => provider.identity_provider_method === 'saml'
    );
    const hasCognitoProvider = awsConfig.Auth.identity_providers.some(
        provider => provider.identity_provider_method === 'cognito'
    );

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
            gap: '20px'
        }}>
            <Box sx={{
                background: 'linear-gradient(135deg, #0050b3 0%, #002766 100%)',
                borderRadius: '8px',
                boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
                padding: '2.5rem',
                textAlign: 'center',
                color: 'white',
                width: '400px',
            }}>
                {/* Single header for both auth methods */}
                <Box sx={{ mb: 4 }}>
                    <img
                        src="/logo.png"
                        alt="MediaLake Logo"
                        style={{
                            height: '40px',
                            marginBottom: '1rem',
                        }}
                    />
                    <h1 style={{
                        fontSize: '1.5rem',
                        fontWeight: '600',
                        margin: '0 0 0.5rem',
                    }}>
                        Welcome to MediaLake
                    </h1>
                    <p style={{
                        fontSize: '0.875rem',
                        color: 'rgba(255, 255, 255, 0.85)',
                        margin: '0',
                        lineHeight: '1.5',
                    }}>
                        A data lake for your media, metadata, and media pipelines.
                    </p>
                </Box>

                <Stack spacing={2} sx={{ mt: 2 }}>
                    {/* SAML Provider Buttons */}
                    {hasSamlProvider && awsConfig.Auth.identity_providers.map(provider => {
                        if (provider.identity_provider_method === 'saml') {
                            return (
                                <Button
                                    key={provider.identity_provider_name}
                                    onClick={() => {
                                        console.log('Initiating SAML login with provider:', provider.identity_provider_name);
                                        signInWithRedirect({
                                            provider: { custom: provider.identity_provider_name }
                                        }).catch(error => {
                                            console.error('SAML redirect error:', error);
                                        });
                                    }}
                                    sx={{
                                        padding: '12px 24px',
                                        fontSize: '1rem',
                                        backgroundColor: 'rgba(255, 255, 255, 0.2)',
                                        color: 'white',
                                        height: '40px',
                                        width: '100%',
                                        textTransform: 'none',
                                        '&:hover': {
                                            backgroundColor: 'rgba(255, 255, 255, 0.3)',
                                        }
                                    }}
                                >
                                    Sign in with {provider.identity_provider_name}
                                </Button>
                            );
                        }
                        return null;
                    })}

                    {/* Divider between SAML and Cognito */}
                    {hasSamlProvider && hasCognitoProvider && (
                        <Divider sx={{ my: 2, borderColor: 'rgba(255, 255, 255, 0.2)' }}>
                            <Typography sx={{ color: 'rgba(255, 255, 255, 0.7)' }}>OR</Typography>
                        </Divider>
                    )}

                    {/* Cognito Login Form */}
                    {hasCognitoProvider && (
                        <Box sx={{
                            '& .amplify-authenticator': {
                                marginBottom: '1rem',
                                maxWidth: 'none',
                                width: '100%',
                            },
                            '& [data-amplify-authenticator]': {
                                background: 'transparent',
                                boxShadow: 'none',
                                maxWidth: 'none',
                                width: '100%',
                            },
                            '& [data-amplify-container]': {
                                padding: '0',
                                maxWidth: 'none',
                                width: '100%',
                            },
                            '& [data-amplify-form]': {
                                padding: '0',
                                maxWidth: 'none',
                                width: '100%',
                            },
                            '& .amplify-button[type="submit"]': {
                                maxWidth: 'none',
                                width: '100%',
                            },
                            '& .amplify-divider, & .amplify-divider--small': {
                                display: 'none',
                            },
                            '& .amplify-tabs': {
                                width: '100%',
                            },
                            '& .amplify-button': {
                                backgroundColor: 'rgba(255, 255, 255, 0.2)',
                                color: 'white',
                                height: '40px',
                                width: '100%',
                                '&:hover': {
                                    backgroundColor: 'rgba(255, 255, 255, 0.3)',
                                },
                            },
                            '& .amplify-field': {
                                '--amplify-components-field-label-color': 'rgba(255, 255, 255, 0.9)',
                                width: '100%',
                                '& .amplify-flex': {
                                    width: '100%',
                                }
                            },
                            '& .amplify-input': {
                                backgroundColor: 'rgba(255, 255, 255, 0.1)',
                                color: 'white',
                                borderColor: 'rgba(255, 255, 255, 0.2)',
                                width: '100%',
                                height: '40px',
                                textAlign: 'center',
                                paddingRight: '40px',
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
                    )}
                </Stack>
            </Box>
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
                    minWidth: 0,
                    height: 'calc(100vh - 64px)',
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
                path: 'pipelines/new',
                element: <PipelineEditorPage />
            },
            {
                path: 'images/:id',
                element: <ImageDetailPage />
            },
            {
                path: 'videos/:id',
                element: <VideoDetailPage />
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

const AppConfigured = () => {
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
