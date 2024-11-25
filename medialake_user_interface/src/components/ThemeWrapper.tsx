import React, { useEffect } from 'react';
import { useTheme } from '@/hooks/useTheme';
import '@/styles/theme.css';

export const ThemeWrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { theme } = useTheme();

    useEffect(() => {
        document.documentElement.setAttribute('data-theme', theme);
    }, [theme]);

    return <>{children}</>;
};
