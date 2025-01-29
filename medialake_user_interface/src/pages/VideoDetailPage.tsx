import React, { useState, useMemo } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { Box, CircularProgress, Typography, Paper, List, ListItem, Divider, Button } from '@mui/material';
import { useAsset } from '../api/hooks/useAssets';
import { RightSidebarProvider, useRightSidebar } from '../components/common/RightSidebar';
import { RecentlyViewedProvider, useTrackRecentlyViewed } from '../contexts/RecentlyViewedContext';
import AssetSidebar from '../components/asset/AssetSidebar';
import BreadcrumbNavigation from '../components/common/BreadcrumbNavigation';
import AssetHeader from '../components/asset/AssetHeader';
import AssetVideo from '../components/asset/AssetVideo';
import { formatCamelCase } from '../utils/stringUtils';
import { TruncatedTextWithTooltip } from '../components/common/TruncatedTextWithTooltip';


const outputFilters = {
    'Image (IFD0)': ['ImageWidth', 'ImageHeight', 'Make', 'Model', 'Software'],
    'EXIF': ['ExposureTime', 'ShutterSpeedValue', 'FNumber', 'ApertureValue', 'ISO', 'LensModel'],
    'GPS': ['GPSLatitude', 'GPSLongitude', 'GPSAltitude'],
    'Thumbnail (IFD1)': ['ImageWidth', 'ImageHeight', 'ThumbnailLength'],
    'IPTC': ['Headline', 'Byline', 'Credit', 'Caption', 'Source', 'Country'],
    'ICC': ['ProfileVersion', 'ProfileClass', 'ColorSpaceData', 'ProfileConnectionSpace', 'ProfileFileSignature', 'DeviceManufacturer', 'RenderingIntent', 'ProfileCreator', 'ProfileDescription'],
    'XMP': ['Creator', 'Title', 'Description', 'Rights'],
    'JFIF (JPEG only)': ['JFIFVersion', 'ResolutionUnit', 'XResolution', 'YResolution'],
    'IHDR (PNG only)': ['Width', 'Height', 'BitDepth', 'ColorType', 'CompressionMethod', 'FilterMethod', 'InterlaceMethod'],
    'Maker Note': [],
    'User Comment': [],
    'Rights': ['UsageTerms', 'CopyrightNotice', 'WebStatement'],
    'IPTC Core': ['CreatorContactInfo', 'Scene'],
    'IPTC Extension': ['PersonInImage', 'LocationCreated'],
    'Photoshop': ['Category', 'SupplementalCategories', 'AuthorsPosition'],
    'PLUS': ['LicenseID', 'ImageCreator', 'CopyrightOwner'],
    'Dublin Core': ['Format', 'Type', 'Identifier'],
    'XMP Media Management': ['DerivedFrom', 'DocumentID', 'InstanceID'],
    'Auxiliary': ['Lens', 'SerialNumber'],
    'Camera Raw Settings': ['Version', 'ProcessVersion', 'WhiteBalance', 'Temperature', 'Tint'],
    'EXIF Extended': ['Gamma', 'CameraOwnerName', 'BodySerialNumber'],
    'XMP Dynamic Media': ['AudioSampleRate', 'AudioChannelType', 'VideoFrameRate', 'StartTimeScale', 'Duration'],
    'Interoperability': ['InteroperabilityIndex', 'InteroperabilityVersion']
};

interface MetadataContentProps {
    data: any;
    depth?: number;
    showAll: boolean;
    category?: string;
}

const MetadataContent: React.FC<MetadataContentProps> = ({ data, depth = 0, showAll, category }) => {
    const sortEntries = (entries: [string, any][]): [string, any][] => {
        if (category && outputFilters[category]) {
            const preferredOrder = outputFilters[category];
            return [
                ...preferredOrder.map(key => entries.find(([k]) => k === key)).filter(Boolean),
                ...entries.filter(([key]) => !preferredOrder.includes(key))
            ];
        }
        return entries;
    };

    if (Array.isArray(data)) {
        const displayData = showAll ? data : data.slice(0, 5);
        return (
            <List dense disablePadding>
                {displayData.map((item, index) => (
                    <ListItem key={index} sx={{ pl: depth * 2 }}>
                        <MetadataContent data={item} depth={depth + 1} showAll={showAll} category={category} />
                    </ListItem>
                ))}
            </List>
        );
    } else if (typeof data === 'object' && data !== null) {
        const entries = Object.entries(data);
        const sortedEntries = sortEntries(entries);
        const displayEntries = showAll ? sortedEntries : sortedEntries.slice(0, 5);

        return (
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 2 }}>
                {displayEntries.map(([key, value]) => (
                    <Box key={key}>
                        <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                            {formatCamelCase(key)}:
                        </Typography>
                        <Box sx={{ pl: 2 }}>
                            <MetadataContent
                                data={value}
                                depth={depth + 1}
                                showAll={showAll}
                                category={category}
                            />
                        </Box>
                    </Box>
                ))}
            </Box>
        );
    } else {
        return <TruncatedTextWithTooltip text={String(data)} />;
    }
};

const VideoDetailContent: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const location = useLocation();
    const { isExpanded } = useRightSidebar();
    const { data: assetData, isLoading, error } = useAsset(id || '');

    const [expandedMetadata, setExpandedMetadata] = useState<{ [key: string]: boolean }>({});
    const [comments, setComments] = useState([
        { user: "John Doe", avatar: "https://mui.com/static/videos/avatar/1.jpg", content: "Great composition!", timestamp: "2023-06-15 09:30:22" },
        { user: "Jane Smith", avatar: "https://mui.com/static/videos/avatar/2.jpg", content: "The lighting is perfect", timestamp: "2023-06-15 10:15:43" },
        { user: "Mike Johnson", avatar: "https://mui.com/static/videos/avatar/3.jpg", content: "Can we adjust the contrast?", timestamp: "2023-06-15 11:22:17" },
    ]);

    const searchParams = new URLSearchParams(location.search);
    const searchTerm = searchParams.get('q') || searchParams.get('searchTerm') || '';

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

    const transformMetadata = (metadata: any) => {
        if (!metadata) return [];

        return Object.entries(metadata).map(([parentCategory, parentData]) => ({
            category: parentCategory,
            subCategories: Object.entries(parentData as object).map(([subCategory, data]) => ({
                category: subCategory,
                data: data,
                count: typeof data === 'object' ? (Array.isArray(data) ? data.length : Object.keys(data).length) : 1
            })),
            count: Object.keys(parentData as object).length
        }));
    };

    const metadataAccordions = useMemo(() => {
        if (!assetData?.data?.asset?.Metadata) return [];
        return transformMetadata(assetData.data.asset.Metadata);
    }, [assetData]);

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


    const toggleMetadataExpansion = (key: string) => {
        setExpandedMetadata(prev => ({ ...prev, [key]: !prev[key] }));
    };
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
            maxWidth: isExpanded ? 'calc(100% - 300px)' : 'calc(100% - 8px)',
            transition: theme => theme.transitions.create(['max-width'], {
                easing: theme.transitions.easing.sharp,
                duration: theme.transitions.duration.enteringScreen,
            }),
            height: '100vh',
            overflow: 'auto',
        }}>
            <Box sx={{ position: 'sticky', top: 0, zIndex: 1200, bgcolor: 'background.default' }}>
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
            </Box>

            <Box sx={{ px: 3, pt: 2 }}>
                <AssetHeader />
            </Box>

            <Box sx={{ px: 3, pt: 2, height: 'calc(100vh - 200px)', display: 'flex', flexDirection: 'column' }}>
                <AssetVideo
                    src={proxyUrl}
                    alt={assetData.data.asset.DigitalSourceAsset.MainRepresentation.ID}
                />
            </Box>

            <Box sx={{ px: 3, pb: 3 }}>
                <Box sx={{ mt: 2 }}>
                    <Paper elevation={3} sx={{ p: 2 }}>
                        <Typography variant="h6">Metadata</Typography>
                        <Divider sx={{ my: 1 }} />
                        {metadataAccordions.map((parentAccordion, parentIndex) => (
                            <Paper key={parentAccordion.category} elevation={1} sx={{ mb: 2 }}>
                                <Typography variant="subtitle1" sx={{ p: 2, fontWeight: 'bold' }}>
                                    {parentAccordion.category} ({parentAccordion.count})
                                </Typography>
                                {parentAccordion.subCategories.map((subCategory, subIndex) => (
                                    <Box key={subCategory.category} sx={{ p: 2 }}>
                                        <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
                                            {subCategory.category} ({subCategory.count})
                                        </Typography>
                                        <MetadataContent
                                            data={subCategory.data}
                                            showAll={expandedMetadata[`${parentIndex}-${subIndex}`]}
                                            category={subCategory.category}
                                        />
                                        <Button
                                            onClick={() => toggleMetadataExpansion(`${parentIndex}-${subIndex}`)}
                                            sx={{ mt: 1 }}
                                        >
                                            {expandedMetadata[`${parentIndex}-${subIndex}`] ? 'Show Less' : 'Show More'}
                                        </Button>
                                    </Box>
                                ))}
                            </Paper>
                        ))}
                    </Paper>
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
