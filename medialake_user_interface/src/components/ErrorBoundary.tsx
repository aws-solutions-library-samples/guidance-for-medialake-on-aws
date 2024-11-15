import React from 'react';
import { Box, Typography, Button } from '@mui/material';
import { useRouteError, useNavigate } from 'react-router-dom';

const ErrorBoundary: React.FC = () => {
    const error = useRouteError();
    const navigate = useNavigate();

    return (
        <Box
            sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100vh',
                gap: 2,
            }}
        >
            <Typography variant="h4">Oops! Something went wrong</Typography>
            <Typography variant="body1" color="text.secondary">
                {error instanceof Error ? error.message : 'An unexpected error occurred'}
            </Typography>
            <Button
                variant="contained"
                color="primary"
                onClick={() => navigate(-1)}
            >
                Go Back
            </Button>
        </Box>
    );
};

export default ErrorBoundary; 