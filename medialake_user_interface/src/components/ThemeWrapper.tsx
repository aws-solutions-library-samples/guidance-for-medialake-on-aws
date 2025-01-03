// components/ThemeWrapper.tsx
import React, { useMemo } from 'react';
import { ThemeProvider as MuiThemeProvider, createTheme, Theme as MuiTheme } from '@mui/material/styles';
import { alpha } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { useTheme } from '../hooks/useTheme';

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
                divider: 'rgba(255, 255, 255, 0.12)',
            } : {
                background: {
                    default: '#f0f2f5',
                    paper: '#ffffff',
                },
                text: {
                    primary: 'rgba(0, 0, 0, 0.87)',
                    secondary: 'rgba(0, 0, 0, 0.6)',
                },
                divider: 'rgba(0, 0, 0, 0.12)',
            }),
        },
        components: {
            MuiTableCell: {
                styleOverrides: {
                    root: ({ theme: muiTheme }) => ({
                        backgroundColor: 'transparent',
                        borderColor: alpha(muiTheme.palette.divider, 0.1),
                        color: muiTheme.palette.text.primary,
                    }),
                    head: ({ theme: muiTheme }) => ({
                        backgroundColor: muiTheme.palette.mode === 'dark'
                            ? alpha(muiTheme.palette.background.default, 0.3)
                            : alpha(muiTheme.palette.background.paper, 0.04),
                        fontWeight: 600,
                    }),
                },
            },
            MuiTableRow: {
                styleOverrides: {
                    root: ({ theme: muiTheme }) => ({
                        backgroundColor: 'transparent',
                        '&:hover': {
                            backgroundColor: alpha(
                                muiTheme.palette.primary.main,
                                0.05
                            ),
                        },
                        '& .MuiTableCell-root': {
                            backgroundColor: 'transparent',
                        }
                    }),
                },
            },
            MuiTableContainer: {
                styleOverrides: {
                    root: ({ theme: muiTheme }) => ({
                        backgroundColor: muiTheme.palette.mode === 'dark'
                            ? muiTheme.palette.background.default
                            : muiTheme.palette.background.paper,
                    }),
                },
            },
            MuiPaper: {
                styleOverrides: {
                    root: ({ theme: muiTheme }) => ({
                        backgroundImage: 'none',
                        backgroundColor: muiTheme.palette.mode === 'dark'
                            ? muiTheme.palette.background.paper
                            : '#ffffff',
                    }),
                },
            },
            MuiCssBaseline: {
                styleOverrides: {
                    body: ({ theme: muiTheme }) => ({
                        scrollbarColor: theme === 'dark'
                            ? '#6b6b6b transparent'
                            : '#959595 transparent',
                        '&::-webkit-scrollbar': {
                            width: '8px',
                            height: '8px',
                        },
                        '&::-webkit-scrollbar-track': {
                            background: 'transparent',
                        },
                        '&::-webkit-scrollbar-thumb': {
                            background: theme === 'dark' ? '#6b6b6b' : '#959595',
                            borderRadius: '4px',
                        },
                        '&::-webkit-scrollbar-thumb:hover': {
                            background: theme === 'dark' ? '#7b7b7b' : '#858585',
                        },
                    }),
                },
            },
        },
    }), [theme]);

    return (
        <MuiThemeProvider theme={muiTheme}>
            <CssBaseline />
            {children}
        </MuiThemeProvider>
    );
};