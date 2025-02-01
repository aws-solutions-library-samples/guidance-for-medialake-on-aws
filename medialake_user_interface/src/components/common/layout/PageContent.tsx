import React from 'react';
import { Box, CircularProgress, Alert } from '@mui/material';

interface PageContentProps {
    isLoading?: boolean;
    error?: Error | null;
    children: React.ReactNode;
}

const LoadingState = () => (
    <Box sx={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center',
        height: '100%',
        minHeight: 200
    }}>
        <CircularProgress />
    </Box>
);

const ErrorState = ({ error }: { error: Error }) => (
    <Box sx={{ p: 2 }}>
        <Alert 
            severity="error"
            sx={{ mb: 2 }}
        >
            {error.message}
        </Alert>
    </Box>
);

const PageContent: React.FC<PageContentProps> = ({ 
    isLoading = false,
    error = null,
    children 
}) => {
    return (
        <Box sx={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            minHeight: 0
        }}>
            {isLoading ? (
                <LoadingState />
            ) : error ? (
                <ErrorState error={error} />
            ) : (
                children
            )}
        </Box>
    );
};

export default PageContent;