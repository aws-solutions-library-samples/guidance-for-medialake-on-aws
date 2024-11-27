import React, { useEffect, useMemo } from 'react';
import { ThemeProvider as MuiThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { useTheme } from '../hooks/useTheme';
import '../styles/theme.css';

export const ThemeWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { theme } = useTheme();

    const muiTheme = useMemo(() => createTheme({
        palette: {
            mode: theme,
            ...(theme === 'dark' ? {
                background: {
                    default: '#121212',
                    paper: '#1e1e1e',
                },
                text: {
                    primary: 'rgba(255, 255, 255, 0.87)',
                    secondary: 'rgba(255, 255, 255, 0.6)',
                },
            } : {
                background: {
                    default: '#f0f2f5',
                    paper: '#ffffff',
                },
                text: {
                    primary: 'rgba(0, 0, 0, 0.87)',
                    secondary: 'rgba(0, 0, 0, 0.6)',
                },
            }),
        },
        components: {
            MuiTableCell: {
                styleOverrides: {
                    root: {
                        color: 'inherit',
                    },
                },
            },
            MuiChip: {
                styleOverrides: {
                    root: {
                        color: 'inherit',
                    },
                },
            },
        },
    }), [theme]);

    useEffect(() => {
        document.documentElement.setAttribute('data-theme', theme);
    }, [theme]);

    return (
        <MuiThemeProvider theme={muiTheme}>
            <CssBaseline />
            {children}
        </MuiThemeProvider>
    );
};
