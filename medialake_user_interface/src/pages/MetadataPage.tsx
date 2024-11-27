import React from 'react';
import { useTranslation } from 'react-i18next';
import { Box, Typography } from '@mui/material';
import ConstructionIcon from '@mui/icons-material/Construction';

const MetadataPage: React.FC = () => {
    const { t } = useTranslation();

    return (
        <Box
            sx={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                minHeight: 'calc(100vh - 100px)', // Account for top bar and padding
                textAlign: 'center',
                gap: 3
            }}
        >
            <ConstructionIcon
                sx={{
                    fontSize: 100,
                    color: 'primary.main',
                    animation: 'pulse 2s infinite ease-in-out'
                }}
            />
            <Typography
                variant="h2"
                component="h1"
                sx={{
                    fontWeight: 600,
                    background: 'linear-gradient(45deg, #007FFF 30%, #0059B2 90%)',
                    backgroundClip: 'text',
                    textFillColor: 'transparent',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent'
                }}
            >
                {t('metadata.title')}
            </Typography>
            <Typography
                variant="h6"
                color="text.secondary"
                sx={{ maxWidth: 600 }}
            >
                {t('metadata.description')}
            </Typography>

            <style>
                {`
          @keyframes pulse {
            0% {
              transform: scale(1);
              opacity: 1;
            }
            50% {
              transform: scale(1.1);
              opacity: 0.8;
            }
            100% {
              transform: scale(1);
              opacity: 1;
            }
          }
        `}
            </style>
        </Box>
    );
};

export default MetadataPage;
