import { useEffect, useState, useCallback } from "react";
import { ThemeProvider } from "@aws-amplify/ui-react";
import SignInPage from "../pages/sign-in"
import { StorageHelper } from "../common/helpers/storage-helper";
import { AuthProvider, useAuth } from "../common/hooks/auth-context";
import { useAuthenticate } from "../common/hooks/authenticate";
import { AwsConfigProvider, useAwsConfig } from '../common/hooks/aws-config-context';
import { CognitoUser } from 'amazon-cognito-identity-js';
import { createTheme, ThemeProvider as MuiThemeProvider } from '@mui/material/styles';

import App from "../App";
import "@aws-amplify/ui-react/styles.css";

interface AuthenticatedAppProps {
    theme: 'light' | 'dark';
}

function AuthenticatedApp({ theme }: AuthenticatedAppProps) {
    const { isAuthenticated, checkAuthStatus, refreshSession } = useAuth();
    const [loginErr, setLoginErr] = useState('');
    const { authenticate, changePassword } = useAuthenticate();
    const awsConfig = useAwsConfig();

    // Create Material UI theme based on the current mode
    const muiTheme = createTheme({
        palette: {
            mode: theme === 'dark' ? 'dark' : 'light',
            primary: {
                main: '#1976d2',
            },
            secondary: {
                main: '#dc004e',
            },
        },
    });

    if (!awsConfig) {
        return <div>Loading AWS configuration...</div>;
    }

    const refreshSessionPeriodically = useCallback(async () => {
        try {
            await refreshSession();
        } catch (error) {
            console.error('Failed to refresh session:', error);
        }
    }, [refreshSession]);

    useEffect(() => {
        checkAuthStatus();

        const refreshInterval = setInterval(() => {
            if (isAuthenticated) {
                refreshSessionPeriodically();
            }
        }, 15 * 60 * 1000); // Refresh every 15 minutes

        return () => clearInterval(refreshInterval);
    }, [isAuthenticated, checkAuthStatus, refreshSessionPeriodically]);

    const handleSignIn = async (email: string, password: string): Promise<{ success: boolean, user?: CognitoUser, type?: string }> => {
        try {
            const result = await authenticate(email, password);
            setLoginErr('');
            checkAuthStatus();

            if (result.type === 'SUCCESS') {
                return { success: true };
            } else if (result.type === 'NEW_PASSWORD_REQUIRED') {
                return { success: false, user: result.user, type: result.type };
            } else {
                console.log('Unexpected authentication result:', result);
                setLoginErr('An unexpected error occurred');
                return { success: false };
            }
        } catch (error: any) {
            console.log(error);
            if (error.error && error.user) {
                console.log("Authentication error:", error.error);
                console.log("User object:", error.user);
                setLoginErr(error.error.message);
                return { success: false, user: error.user };
            } else {
                console.log("Unexpected error:", error);
                setLoginErr(error.message || 'An unexpected error occurred');
                return { success: false };
            }
        }
    };

    return (
        <ThemeProvider
            theme={{
                name: "default-theme",
                overrides: [],
            }}
            colorMode={theme}
        >
            <MuiThemeProvider theme={muiTheme}>
                {isAuthenticated ? (
                    <App />
                ) : (
                    <SignInPage onSignIn={handleSignIn} loginError={loginErr} onChangePassword={changePassword} />
                )}
            </MuiThemeProvider>
        </ThemeProvider>
    );
}

export default function AppConfigured() {
    const [theme, setTheme] = useState<'light' | 'dark'>(
        typeof StorageHelper.getTheme === 'function'
            ? StorageHelper.getTheme()
            : 'light'
    );

    useEffect(() => {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (
                    mutation.type === "attributes" &&
                    mutation.attributeName === "style"
                ) {
                    const newValue =
                        document.documentElement.style.getPropertyValue(
                            "--app-color-scheme"
                        );

                    const mode = newValue === "dark" ? 'dark' : 'light';
                    if (mode !== theme) {
                        setTheme(mode);
                    }
                }
            });
        });

        observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ["style"],
        });

        return () => {
            observer.disconnect();
        };
    }, [theme]);

    return (
        <AuthProvider>
            <AwsConfigProvider>
                <AuthenticatedApp theme={theme} />
            </AwsConfigProvider>
        </AuthProvider>
    );
}
