import React from 'react';
import { useTranslation } from 'react-i18next';
import {
    Box,
    Typography,
    Paper,
    IconButton,
    useTheme,
    alpha,
    Card,
    CardContent,
    Tooltip,
} from '@mui/material';
import {
    ChevronLeft as ChevronLeftIcon,
    ChevronRight as ChevronRightIcon,
    Storage as StorageIcon,
} from '@mui/icons-material';
import { S3Explorer } from '../features/home/S3Explorer';
import { useGetConnectors } from '../api/hooks/useConnectors';

const AssetsPage: React.FC = () => {
    const { t } = useTranslation();
    const theme = useTheme();
    const [selectedConnector, setSelectedConnector] = React.useState<string | null>(null);
    const { data: connectorsResponse, isLoading } = useGetConnectors();
    const carouselRef = React.useRef<HTMLDivElement>(null);

    const connectors = connectorsResponse?.data.connectors || [];

    const scroll = (direction: 'left' | 'right') => {
        if (carouselRef.current) {
            const scrollAmount = 300;
            const newScrollLeft = carouselRef.current.scrollLeft + (direction === 'left' ? -scrollAmount : scrollAmount);
            carouselRef.current.scrollTo({
                left: newScrollLeft,
                behavior: 'smooth'
            });
        }
    };

    return (
        <Box sx={{ p: 4, height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Typography variant="h4" sx={{
                fontWeight: 700,
                mb: 3,
                background: `linear-gradient(45deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
                backgroundClip: 'text',
                WebkitBackgroundClip: 'text',
                color: 'transparent',
            }}>
                {t('assets.title')}
            </Typography>

            <Paper elevation={0} sx={{
                p: 3,
                mb: 3,
                borderRadius: '12px',
                border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                backgroundColor: theme.palette.background.paper,
            }}>
                <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                    {t('assets.connectedStorage')}
                </Typography>

                <Box sx={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                    <IconButton
                        onClick={() => scroll('left')}
                        sx={{
                            position: 'absolute',
                            left: -16,
                            zIndex: 2,
                            backgroundColor: theme.palette.background.paper,
                            boxShadow: theme.shadows[2],
                            '&:hover': {
                                backgroundColor: alpha(theme.palette.primary.main, 0.1),
                            },
                        }}
                    >
                        <ChevronLeftIcon />
                    </IconButton>

                    <Box
                        ref={carouselRef}
                        sx={{
                            display: 'flex',
                            overflowX: 'hidden',
                            gap: 2,
                            px: 2,
                            scrollBehavior: 'smooth',
                            '&::-webkit-scrollbar': {
                                display: 'none'
                            },
                        }}
                    >
                        {connectors.map((connector) => (
                            <Card
                                key={connector.id}
                                elevation={0}
                                onClick={() => setSelectedConnector(connector.id)}
                                sx={{
                                    minWidth: 200,
                                    cursor: 'pointer',
                                    border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                    borderRadius: '12px',
                                    backgroundColor: selectedConnector === connector.id
                                        ? alpha(theme.palette.primary.main, 0.1)
                                        : theme.palette.background.paper,
                                    transition: 'all 0.2s ease-in-out',
                                    '&:hover': {
                                        transform: 'translateY(-4px)',
                                        boxShadow: `0 4px 20px ${alpha(theme.palette.common.black, 0.1)}`,
                                    },
                                }}
                            >
                                <CardContent>
                                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                        <StorageIcon sx={{
                                            color: selectedConnector === connector.id
                                                ? theme.palette.primary.main
                                                : theme.palette.text.secondary
                                        }} />
                                        <Typography variant="subtitle1" sx={{
                                            fontWeight: 600,
                                            color: selectedConnector === connector.id
                                                ? theme.palette.primary.main
                                                : theme.palette.text.primary
                                        }}>
                                            {connector.name}
                                        </Typography>
                                    </Box>
                                    <Typography variant="body2" color="text.secondary">
                                        {connector.type.toUpperCase()}
                                    </Typography>
                                </CardContent>
                            </Card>
                        ))}
                    </Box>

                    <IconButton
                        onClick={() => scroll('right')}
                        sx={{
                            position: 'absolute',
                            right: -16,
                            zIndex: 2,
                            backgroundColor: theme.palette.background.paper,
                            boxShadow: theme.shadows[2],
                            '&:hover': {
                                backgroundColor: alpha(theme.palette.primary.main, 0.1),
                            },
                        }}
                    >
                        <ChevronRightIcon />
                    </IconButton>
                </Box>
            </Paper>

            {selectedConnector && (
                <Paper elevation={0} sx={{
                    flex: 1,
                    borderRadius: '12px',
                    border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                    backgroundColor: theme.palette.background.paper,
                    overflow: 'hidden',
                }}>
                    <S3Explorer connectorId={selectedConnector} />
                </Paper>
            )}
        </Box>
    );
};

export default AssetsPage;
