import React from 'react';
import { Box, Paper, Typography, Alert, AlertTitle, useTheme } from '@mui/material';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';

interface ErrorDisplayProps {
    title: string;
    message: string;
    detailedMessage?: string;
}

const ErrorDisplay: React.FC<ErrorDisplayProps> = ({ title, message, detailedMessage }) => {
    const theme = useTheme();
    
    return (
        <Paper 
            elevation={2}
            sx={{
                p: 4,
                mt: 3,
                mb: 3,
                borderRadius: 2,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                textAlign: 'center',
                maxWidth: '800px',
                mx: 'auto',
                backgroundColor: theme.palette.mode === 'dark' 
                    ? theme.palette.background.paper 
                    : theme.palette.grey[50]
            }}
        >
            <ErrorOutlineIcon 
                sx={{ 
                    fontSize: 64, 
                    color: theme.palette.error.main,
                    mb: 2
                }} 
            />
            
            <Typography variant="h5" component="h2" gutterBottom fontWeight="medium">
                {title}
            </Typography>
            
            <Typography variant="body1" color="text.secondary" paragraph>
                {message}
            </Typography>
            
            {detailedMessage && (
                <Alert 
                    severity="error" 
                    variant="outlined"
                    sx={{ 
                        mt: 2, 
                        width: '100%',
                        textAlign: 'left',
                        '& .MuiAlert-message': {
                            width: '100%'
                        }
                    }}
                >
                    <AlertTitle>Detailed Message</AlertTitle>
                    {detailedMessage}
                </Alert>
            )}
        </Paper>
    );
};

export default ErrorDisplay; 