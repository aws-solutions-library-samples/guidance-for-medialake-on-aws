import React from 'react';
import { Box, Typography, useTheme } from '@mui/material';

interface PageHeaderProps {
    title: string;
    description: string;
    action?: React.ReactNode;
}

const PageHeader: React.FC<PageHeaderProps> = ({ title, description, action }) => {
    const theme = useTheme();
    
    return (
        <Box sx={{ mb: 4 }}>
            <Box sx={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'flex-start',
                mb: 3
            }}>
                <Box>
                    <Typography 
                        variant="h4" 
                        sx={{
                            fontWeight: 700,
                            mb: 1,
                            color: theme.palette.primary.main
                        }}
                    >
                        {title}
                    </Typography>
                    <Typography 
                        variant="body1" 
                        sx={{ 
                            color: theme.palette.text.secondary,
                            maxWidth: '600px'
                        }}
                    >
                        {description}
                    </Typography>
                </Box>
                {action}
            </Box>
        </Box>
    );
};

export default PageHeader;