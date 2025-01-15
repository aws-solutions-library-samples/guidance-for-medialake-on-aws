import React, { useState, useMemo } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { Box, CircularProgress } from '@mui/material';
import { useAsset } from '../api/hooks/useAssets';
import { RightSidebarProvider, useRightSidebar } from '../components/common/RightSidebar';
import { RecentlyViewedProvider, useTrackRecentlyViewed } from '../contexts/RecentlyViewedContext';
import AssetSidebar from '../components/asset/AssetSidebar';
import BreadcrumbNavigation from '../components/common/BreadcrumbNavigation';
import AssetHeader from '../components/asset/AssetHeader';
import AssetVideo from '../components/asset/AssetVideo';
import AssetMetadataTabs from '../components/asset/AssetMetadataTabs';

const VideoDetailContent: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const { data: assetData, isLoading, error } = useAsset(id || '');
    const navigate = useNavigate();
    const location = useLocation();
    const searchParams = new URLSearchParams(location.search);
    const searchTerm = searchParams.get('q') || searchParams.get('searchTerm') || '';
    const { isExpanded } = useRightSidebar();

    const [comments, setComments] = useState([
        { user: "John Doe", avatar: "https://mui.com/static/videos/avatar/1.jpg", content: "Great composition!", timestamp: "2023-06-15 09:30:22" },
        { user: "Jane Smith", avatar: "https://mui.com/static/videos/avatar/2.jpg", content: "The lighting is perfect", timestamp: "2023-06-15 10:15:43" },
        { user: "Mike Johnson", avatar: "https://mui.com/static/videos/avatar/3.jpg", content: "Can we adjust the contrast?", timestamp: "2023-06-15 11:22:17" },
    ]);

    const handleAddComment = (comment: string) => {
        const now = new Date();
        const formattedTimestamp = now.toLocaleString('en-US', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        }).replace(/(\d+)\/(\d+)\/(\d+),/, '$3-$1-$2');

        const newComment = {
            user: "Current User",
            avatar: "https://mui.com/static/videos/avatar/1.jpg",
            content: comment,
            timestamp: formattedTimestamp
        };
        setComments([...comments, newComment]);
    };

    const versions = useMemo(() => {
        if (!assetData?.data?.asset) return [];
        return [
            {
                id: assetData.data.asset.DigitalSourceAsset.MainRepresentation.ID,
                src: assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.FullPath,
                type: 'Original',
                format: assetData.data.asset.DigitalSourceAsset.MainRepresentation.Format,
                fileSize: assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size.toString(),
                description: 'Original high resolution version',
            },
            ...assetData.data.asset.DerivedRepresentations.map(rep => ({
                id: rep.ID,
                src: rep.StorageInfo.PrimaryLocation.ObjectKey.FullPath,
                type: rep.Purpose.charAt(0).toUpperCase() + rep.Purpose.slice(1),
                format: rep.Format,
                fileSize: rep.StorageInfo.PrimaryLocation.FileInfo.Size.toString(),
                description: `${rep.Purpose} version`,
            }))
        ];
    }, [assetData]);

    const metadataFields = useMemo(() => {
        if (!assetData?.data?.asset) return {
            summary: [],
            descriptive: [],
            technical: []
        };

        return {
            summary: [
                { label: 'Title', value: 'Winter Expedition Base Camp' },
                { label: 'Type', value: 'Video' },
                { label: 'Duration', value: '00:15' }
            ],
            descriptive: [
                { label: 'Description', value: 'Base camp footage from winter expedition' },
                { label: 'Keywords', value: 'winter, expedition, base camp' },
                { label: 'Location', value: 'Mount Everest' }
            ],
            technical: [
                { label: 'Format', value: assetData.data.asset.DigitalSourceAsset.MainRepresentation.Format },
                { label: 'File Size', value: assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size },
                { label: 'Created Date', value: '2024-01-07' }
            ]
        };
    }, [assetData]);

    const activityLog = [
        { user: "John Doe", action: "Uploaded video", timestamp: "2024-01-07 09:30:22" },
        { user: "AI Pipeline", action: "Generated metadata", timestamp: "2024-01-07 09:31:05" },
        { user: "Jane Smith", action: "Added tags", timestamp: "2024-01-07 10:15:43" }
    ];

    // Track this asset in recently viewed
    useTrackRecentlyViewed(
        assetData ? {
            id: assetData.data.asset.DigitalSourceAsset.MainRepresentation.ID,
            title: assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name,
            type: assetData.data.asset.DigitalSourceAsset.Type.toLowerCase() as "video",
            path: `/${assetData.data.asset.DigitalSourceAsset.Type.toLowerCase()}s/${assetData.data.asset.InventoryID}`,
            searchTerm: searchTerm,
            metadata: {
                duration: '00:15',
                fileSize: `${assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size} bytes`,
                dimensions: '1920x1080',
                creator: 'John Doe'
            }
        } : null
    );

    if (isLoading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
                <CircularProgress />
            </Box>
        );
    }

    if (error || !assetData) {
        return (
            <Box sx={{ p: 3 }}>
                <BreadcrumbNavigation
                    searchTerm={searchTerm}
                    currentResult={48}
                    totalResults={156}
                    onBack={() => navigate(`/search${searchTerm ? `?q=${encodeURIComponent(searchTerm)}` : ''}`)}
                    onPrevious={() => navigate(-1)}
                    onNext={() => navigate(1)}
                />
            </Box>
        );
    }

    const proxyUrl = (() => {
        const proxyRep = assetData.data.asset.DerivedRepresentations.find(rep => rep.Purpose === 'proxy');
        return proxyRep?.URL || assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.FullPath;
    })();

    return (
        <Box sx={{
            display: 'flex',
            flexDirection: 'column',
            height: '100vh',
            maxWidth: isExpanded ? 'calc(100% - 300px)' : 'calc(100% - 8px)',
            transition: theme => theme.transitions.create(['max-width'], {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.enteringScreen,
            }),
        }}>
            {/* Fixed header section */}
            <Box sx={{
                position: 'sticky',
                top: 0,
                zIndex: 1200,
                bgcolor: 'background.default'
            }}>
                <BreadcrumbNavigation
                    searchTerm={searchTerm}
                    currentResult={48}
                    totalResults={156}
                    onBack={() => navigate(`/search${searchTerm ? `?q=${encodeURIComponent(searchTerm)}` : ''}`)}
                    onPrevious={() => navigate(-1)}
                    onNext={() => navigate(1)}
                    assetName={assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name}
                    assetId={assetData.data.asset.InventoryID}
                    assetType="Video"
                />
                <Box sx={{ px: 3, pt: 2 }}>
                    <AssetHeader />
                </Box>
            </Box>

            {/* Scrollable content */}
            <Box sx={{
                display: 'flex',
                flexDirection: 'column',
                flex: 1,
                overflow: 'auto',
                gap: 3,
                px: 3,
                pb: 3
            }}>
                {/* Fixed video section */}
                <Box sx={{
                    position: 'sticky',
                    top: 120,
                    zIndex: 1100,
                    bgcolor: 'background.default',
                    pt: 2
                }}>
                    <AssetVideo
                        src={proxyUrl}
                        alt={assetData.data.asset.DigitalSourceAsset.MainRepresentation.ID}
                    />
                </Box>

                {/* Scrollable metadata section */}
                <Box sx={{ flex: 1 }}>
                    <AssetMetadataTabs
                        summary={metadataFields.summary}
                        descriptive={metadataFields.descriptive}
                        technical={metadataFields.technical}
                        activityLog={activityLog}
                    />
                </Box>
            </Box>

            <AssetSidebar
                versions={versions}
                comments={comments}
                onAddComment={handleAddComment}
            />
        </Box>
    );
};

const VideoDetailPage: React.FC = () => {
    return (
        <RecentlyViewedProvider>
            <RightSidebarProvider>
                <VideoDetailContent />
            </RightSidebarProvider>
        </RecentlyViewedProvider>
    );
};

export default VideoDetailPage;
