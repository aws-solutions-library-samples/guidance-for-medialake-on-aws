import React from 'react';
import { Box, Grid, Typography, Paper, useTheme, useMediaQuery, Stack, CircularProgress } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useDirection } from '../contexts/DirectionContext';
import { useNavigate } from 'react-router-dom';
import FavoriteIcon from '@mui/icons-material/Favorite';
import CollectionsIcon from '@mui/icons-material/Collections';
import ShareIcon from '@mui/icons-material/Share';
import { useGetFavorites, useRemoveFavorite } from '../api/hooks/useFavorites';
import AssetCard from '../components/shared/AssetCard';
import { useSidebar } from '../contexts/SidebarContext';
import { drawerWidth, collapsedDrawerWidth } from '../constants';
import { useFeatureFlag } from '../contexts/FeatureFlagsContext';

const FeatureCard: React.FC<{
    title: string;
    icon: React.ReactNode;
}> = ({ title, icon }) => {
    const { t } = useTranslation();
    const { direction } = useDirection();
    const isRTL = direction === 'rtl';
    return (
        <Paper
            elevation={0}
            sx={{
                p: 3,
                height: '100%',
                borderRadius: 2,
                backgroundColor: 'background.paper',
                border: '1px solid',
                borderColor: 'divider',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                textAlign: isRTL ? 'right' : 'center',
                transition: 'transform 0.2s ease-in-out',
                '&:hover': {
                    transform: 'translateY(-4px)',
                }
            }}
        >
            <Box sx={{
                color: 'primary.main',
                mb: 2,
                '& svg': {
                    fontSize: 48
                }
            }}>
                {icon}
            </Box>
            <Typography variant="h6" gutterBottom>
                {title}
            </Typography>
            <Typography
                variant="body2"
                color="text.secondary"
                sx={{ mt: 1 }}
            >
                {t('home.comingSoon')}
            </Typography>
        </Paper>
    );
};

const Home: React.FC = () => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const { t } = useTranslation();
    const { direction } = useDirection();
    const isRTL = direction === 'rtl';
    const navigate = useNavigate();
    const { isCollapsed } = useSidebar();
    
    const isFavoritesEnabled = useFeatureFlag('user-favorites-enabled', false);
    
    // Fetch user's favorite assets
    const { data: unsortedFavorites, isLoading, error } = useGetFavorites('ASSET');
    const { mutate: removeFavorite } = useRemoveFavorite();
    
    // Sort favorites by addedAt timestamp in descending order (newest first)
    const favorites = React.useMemo(() => {
        if (!unsortedFavorites) return [];
        
        return [...unsortedFavorites].sort((a, b) => {
            // If both have addedAt timestamps, compare them
            if (a.addedAt && b.addedAt) {
                return new Date(b.addedAt).getTime() - new Date(a.addedAt).getTime();
            }
            
            // If only a has addedAt, it should come first (newer)
            if (a.addedAt && !b.addedAt) {
                return -1;
            }
            
            // If only b has addedAt, it should come first (newer)
            if (!a.addedAt && b.addedAt) {
                return 1;
            }
            
            // If neither has addedAt, maintain original order
            return 0;
        });
    }, [unsortedFavorites]);
    
    // Handle clicking on an asset to navigate to its detail page
    const handleAssetClick = (assetId: string, assetType: string) => {
        const pathPrefix = assetType.toLowerCase() === 'audio' ? '/audio/' : `/${assetType.toLowerCase()}s/`;
        navigate(`${pathPrefix}${assetId}`);
    };

    // Handle toggling favorite status
    const handleFavoriteToggle = (assetId: string, itemType: string, event: React.MouseEvent<HTMLElement>) => {
        event.stopPropagation();
        removeFavorite({ itemId: assetId, itemType });
    };

    return (
        <Box
            component="main"
            sx={{
                position: 'fixed',
                top: 64,
                ...(isRTL
                    ? { left: 0, right: isCollapsed ? collapsedDrawerWidth : drawerWidth }
                    : { left: isCollapsed ? collapsedDrawerWidth : drawerWidth, right: 0 }),
                bottom: 0,
                bgcolor: 'background.default',
                overflowY: 'auto',
                overflowX: 'hidden',
                textAlign: isRTL ? 'right' : 'left',
                transition: theme => theme.transitions.create(['left', 'right'], {
                    easing: theme.transitions.easing.sharp,
                    duration: theme.transitions.duration.leavingScreen,
                }),
            }}
        >
            <Box sx={{ p: { xs: 2, sm: 3 } }}>
                <Box sx={{
                    mb: 6,
                    maxWidth: 800,
                    mx: 'auto',
                    // Remove textAlign property to let children control their own alignment
                }}>
                    <Typography
                        variant="h3"
                        component="h1"
                        sx={{
                            fontWeight: 700,
                            color: 'primary.main',
                            mb: 2,
                            textAlign: 'center' // Force center alignment regardless of parent
                        }}
                    >
                        {t('app.branding.name')}
                    </Typography>
                    <Typography
                        variant="h5"
                        color="text.secondary"
                        sx={{ mb: 4, textAlign: 'center' }} // Force center alignment
                    >
                        {t('home.description')}
                    </Typography>
                </Box>

                <Grid container spacing={4} sx={{ maxWidth: 1200, mx: 'auto' }}>
                    <Grid item xs={12} md={4}>
                        <FeatureCard
                            title={t('home.favorites')}
                            icon={<FavoriteIcon />}
                        />
                    </Grid>
                    <Grid item xs={12} md={4}>
                        <FeatureCard
                            title={t('home.collections')}
                            icon={<CollectionsIcon />}
                        />
                    </Grid>
                    <Grid item xs={12} md={4}>
                        <FeatureCard
                            title={t('home.sharing')}
                            icon={<ShareIcon />}
                        />
                    </Grid>
                </Grid>
                
                {/* User Favorites Section - Feature Flagged */}
                {isFavoritesEnabled && (
                    <Box sx={{ mt: 6, width: '100%' }}>
                        <Typography variant="h5" component="h2" sx={{ mb: 2 }}>
                            {t('home.yourFavoriteAssets', 'Your Favorite Assets')}
                        </Typography>
                        
                        {/* Loading state */}
                        {isLoading && (
                            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '200px' }}>
                                <CircularProgress />
                            </Box>
                        )}
                        
                        {/* Error state */}
                        {error && (
                            <Typography color="error">
                                {t('home.errorLoadingFavorites', 'Error loading favorites')}: {error.message}
                            </Typography>
                        )}
                        
                        {/* Empty state */}
                        {!isLoading && !error && (!favorites || favorites.length === 0) && (
                            <Typography color="text.secondary">
                                {t('home.noFavoriteAssets', 'No favorite assets yet')}
                            </Typography>
                        )}
                        
                        {/* Favorites list */}
                        {!isLoading && !error && favorites && favorites.length > 0 && (
                            <Stack
                                direction="row"
                                spacing={2}
                                sx={{
                                    overflowX: 'auto',
                                    pb: 2,
                                    pt: 1, /* Add padding to the top to prevent cropping on hover */
                                    '&::-webkit-scrollbar': {
                                        height: '8px',
                                    },
                                    '&::-webkit-scrollbar-track': {
                                        backgroundColor: 'rgba(0,0,0,0.05)',
                                        borderRadius: '4px',
                                    },
                                    '&::-webkit-scrollbar-thumb': {
                                        backgroundColor: 'rgba(0,0,0,0.2)',
                                        borderRadius: '4px',
                                    }
                                }}
                            >
                                {favorites.map((favorite) => (
                                    <Box
                                        key={favorite.itemId}
                                        sx={{
                                            minWidth: '250px',
                                            maxWidth: '250px'
                                        }}
                                    >
                                        <AssetCard
                                            id={favorite.itemId}
                                            name={favorite.metadata?.objectName || favorite.metadata?.name || favorite.itemId}
                                            thumbnailUrl={favorite.metadata?.thumbnailUrl || ''}
                                            assetType={favorite.metadata?.assetType || 'Unknown'}
                                            fields={[
                                                { id: 'name', label: 'Name', visible: true },
                                                { id: 'type', label: 'Type', visible: true }
                                            ]}
                                            renderField={(fieldId) => {
                                                if (fieldId === 'name') return favorite.metadata?.objectName || favorite.metadata?.name || favorite.itemId;
                                                if (fieldId === 'type') return favorite.metadata?.assetType || 'Unknown';
                                                return '';
                                            }}
                                            onAssetClick={() => handleAssetClick(favorite.itemId, favorite.metadata?.assetType || 'Unknown')}
                                            onDeleteClick={() => {}} // Not used in this context
                                            onDownloadClick={() => {}} // Not used in this context
                                            isFavorite={true}
                                            onFavoriteToggle={(e) => handleFavoriteToggle(favorite.itemId, favorite.itemType, e)}
                                            cardSize="medium"
                                            aspectRatio="square"
                                            thumbnailScale="fill"
                                            showMetadata={true}
                                        />
                                    </Box>
                                ))}
                            </Stack>
                        )}
                    </Box>
                )}

            </Box>
        </Box>
    );
};

export default Home;
