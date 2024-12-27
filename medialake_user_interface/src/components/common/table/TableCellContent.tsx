// TableCellContent.tsx
import React from 'react';
import { Box, Typography, useTheme } from '@mui/material';

interface TableCellContentProps {
    children: React.ReactNode;
    variant?: 'default' | 'primary' | 'secondary';
    wordBreak?: 'normal' | 'break-all' | 'break-word' | 'keep-all';
}

export const TableCellContent: React.FC<TableCellContentProps> = ({
    children,
    variant = 'default',
    wordBreak = 'break-word',
}) => {
    const theme = useTheme();

    const getColor = () => {
        switch (variant) {
            case 'primary':
                return theme.palette.primary.main;
            case 'secondary':
                return theme.palette.text.secondary;
            default:
                return theme.palette.text.primary;
        }
    };

    return (
        <Box sx={{
            width: '100%',
            overflow: 'visible',
            userSelect: 'text',
        }}>
            <Typography
                variant="body2"
                sx={{
                    color: getColor(),
                    wordBreak,
                    whiteSpace: 'normal',
                    width: '100%',
                    userSelect: 'text',
                }}
            >
                {children}
            </Typography>
        </Box>
    );
};
