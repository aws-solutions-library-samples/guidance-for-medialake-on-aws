import React, { useState, useMemo, useCallback,useRef } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  CircularProgress,
  Typography,
  Paper,
  List,
  ListItem,
  Divider,
  Button,
  Tabs,
  Tab,
  Grid,
  Card,
  CardContent,
  Chip,
  useTheme,
  alpha
} from '@mui/material';
import { useAsset } from '../api/hooks/useAssets';
import { RightSidebarProvider, useRightSidebar } from '../components/common/RightSidebar';
import { RecentlyViewedProvider, useTrackRecentlyViewed } from '../contexts/RecentlyViewedContext';
import AssetSidebar from '../components/asset/AssetSidebar';
import BreadcrumbNavigation from '../components/common/BreadcrumbNavigation';
import AssetHeader from '../components/asset/AssetHeader';
import AssetVideo from '../components/asset/AssetVideo';
import { formatCamelCase } from '../utils/stringUtils';
import { TruncatedTextWithTooltip } from '../components/common/TruncatedTextWithTooltip';
import { formatLocalDateTime } from '@/shared/utils/dateUtils';
import { SimpleTreeView } from '@mui/x-tree-view/SimpleTreeView';
import { TreeItem } from '@mui/x-tree-view/TreeItem';
import { Chip as MuiChip } from '@mui/material';
import { RelatedItemsView } from '../components/shared/RelatedItemsView';
import { RelatedVersionsResponse, AssetResponse } from '../api/types/asset.types';

// MUI Icons
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import CodeOutlinedIcon from '@mui/icons-material/CodeOutlined';
import LinkOutlinedIcon from '@mui/icons-material/LinkOutlined';



import { VideoViewer, VideoViewerRef } from '../components/common/VideoViewer';

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

// Tab content components
const SummaryTab: React.FC<{ metadataFields: any }> = ({ metadataFields }) => {
    const theme = useTheme();
    
    // Create summary data from metadata fields
    const summaryData = [
        {
            label: 'Title',
            value: metadataFields.summary.find((item: any) => item.label === 'Title')?.value || 'Unknown',
            icon: <DescriptionOutlinedIcon fontSize="small" sx={{ color: theme.palette.primary.main }} />
        },
        {
            label: 'Type',
            value: metadataFields.summary.find((item: any) => item.label === 'Type')?.value || 'Video',
            icon: <InfoOutlinedIcon fontSize="small" sx={{ color: theme.palette.primary.main }} />
        },
        {
            label: 'Duration',
            value: metadataFields.summary.find((item: any) => item.label === 'Duration')?.value || 'Unknown',
            icon: <InfoOutlinedIcon fontSize="small" sx={{ color: theme.palette.primary.main }} />
        },
        {
            label: 'Format',
            value: metadataFields.technical.find((item: any) => item.label === 'Format')?.value || 'Unknown',
            icon: <CodeOutlinedIcon fontSize="small" sx={{ color: theme.palette.primary.main }} />
        },
        {
            label: 'File Size',
            value: metadataFields.technical.find((item: any) => item.label === 'File Size')?.value || 'Unknown',
            icon: <InfoOutlinedIcon fontSize="small" sx={{ color: theme.palette.primary.main }} />
        },
        {
            label: 'Date Created',
            value: metadataFields.technical.find((item: any) => item.label === 'Date Created')?.value || 'Unknown',
            icon: <InfoOutlinedIcon fontSize="small" sx={{ color: theme.palette.primary.main }} />
        }
    ];

    return (
        <Grid container spacing={3}>
            {summaryData.map((field, index) => (
                <Grid item xs={12} sm={6} md={4} key={index}>
                    <Card
                        variant="outlined"
                        sx={{
                            height: '100%',
                            transition: 'all 0.2s ease-in-out',
                            '&:hover': {
                                boxShadow: `0 4px 8px ${alpha(theme.palette.common.black, 0.1)}`,
                                transform: 'translateY(-2px)'
                            }
                        }}
                    >
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                                {field.icon}
                                <Typography
                                    variant="subtitle2"
                                    sx={{
                                        ml: 1,
                                        fontWeight: 600,
                                        color: theme.palette.text.secondary
                                    }}
                                >
                                    {field.label}
                                </Typography>
                            </Box>
                            <Typography
                                variant="body1"
                                sx={{
                                    fontWeight: 500,
                                    wordBreak: 'break-word'
                                }}
                            >
                                {field.value}
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>
            ))}
        </Grid>
    );
};

const TechnicalMetadataTab: React.FC<{ metadataAccordions: any[] }> = ({ metadataAccordions }) => {
    const theme = useTheme();
    
    return (
        <Box sx={{
            maxHeight: '600px',
            overflowY: 'auto',
            borderRadius: 1,
            '&::-webkit-scrollbar': {
                width: '8px',
            },
            '&::-webkit-scrollbar-track': {
                backgroundColor: alpha(theme.palette.primary.main, 0.05),
            },
            '&::-webkit-scrollbar-thumb': {
                backgroundColor: alpha(theme.palette.primary.main, 0.2),
                borderRadius: '4px',
                '&:hover': {
                    backgroundColor: alpha(theme.palette.primary.main, 0.3),
                }
            }
        }}>
            <SimpleTreeView
                sx={{
                    flexGrow: 1,
                    '& .MuiTreeItem-root': {
                        padding: '4px 0',
                    },
                    '& .MuiTreeItem-content': {
                        padding: '4px 8px',
                        borderRadius: '4px',
                        '&:hover': {
                            backgroundColor: alpha(theme.palette.primary.main, 0.05),
                        },
                    },
                    '& .MuiTreeItem-label': {
                        fontWeight: 500,
                    },
                    '& .MuiTreeItem-group': {
                        marginLeft: '24px',
                        borderLeft: `1px dashed ${alpha(theme.palette.text.primary, 0.2)}`,
                        paddingLeft: '8px',
                    }
                }}
                slots={{
                    collapseIcon: ExpandMoreIcon,
                    expandIcon: ChevronRightIcon
                }}
            >
                {metadataAccordions.map((parentAccordion, parentIndex) => (
                    <TreeItem
                        key={parentIndex}
                        itemId={`parent-${parentIndex}`}
                        label={
                            <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                                    {parentAccordion.category}
                                </Typography>
                                <Chip
                                    size="small"
                                    label={parentAccordion.count}
                                    sx={{
                                        ml: 1,
                                        height: '20px',
                                        fontSize: '0.7rem',
                                        backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                        color: theme.palette.primary.main
                                    }}
                                />
                            </Box>
                        }
                    >
                        {parentAccordion.subCategories.map((subCategory, subIndex) => (
                            <TreeItem
                                key={`${parentIndex}-${subIndex}`}
                                itemId={`${parentIndex}-${subIndex}`}
                                label={
                                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                        <Typography variant="body2">
                                            {subCategory.category}
                                        </Typography>
                                        <Chip
                                            size="small"
                                            label={subCategory.count}
                                            sx={{
                                                ml: 1,
                                                height: '18px',
                                                fontSize: '0.65rem',
                                                backgroundColor: alpha(theme.palette.secondary.main, 0.1),
                                                color: theme.palette.secondary.main
                                            }}
                                        />
                                    </Box>
                                }
                            >
                                <Box sx={{
                                    p: 2,
                                    backgroundColor: alpha(theme.palette.background.paper, 0.5),
                                    borderRadius: 1,
                                    mt: 1
                                }}>
                                    <MetadataContent
                                        data={subCategory.data}
                                        showAll={true}
                                        category={subCategory.category}
                                    />
                                </Box>
                            </TreeItem>
                        ))}
                    </TreeItem>
                ))}
            </SimpleTreeView>
        </Box>
    );
};

const DescriptorMetadataTab: React.FC<{ metadataFields: any }> = ({ metadataFields }) => {
    const theme = useTheme();
    
    // Create descriptive data from metadata fields
    const descriptiveData = metadataFields.descriptive.map((item: any) => ({
        label: item.label,
        value: item.value,
        icon: <DescriptionOutlinedIcon fontSize="small" sx={{ color: theme.palette.secondary.main }} />
    }));

    return (
        <Box sx={{ p: 2, backgroundColor: alpha(theme.palette.background.paper, 0.5), borderRadius: 1 }}>
            <Grid container spacing={2}>
                {descriptiveData.map((field, index) => (
                    <Grid item xs={12} key={index}>
                        <Card variant="outlined" sx={{
                            p: 2,
                            transition: 'all 0.2s ease-in-out',
                            '&:hover': {
                                boxShadow: `0 2px 4px ${alpha(theme.palette.common.black, 0.1)}`,
                            }
                        }}>
                            <Box sx={{ display: 'flex', alignItems: 'flex-start' }}>
                                <Box sx={{
                                    mr: 2,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    backgroundColor: alpha(theme.palette.secondary.main, 0.1),
                                    borderRadius: '50%',
                                    p: 1
                                }}>
                                    {field.icon}
                                </Box>
                                <Box>
                                    <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 0.5 }}>
                                        {field.label}
                                    </Typography>
                                    <Typography variant="body2" sx={{ color: theme.palette.text.secondary }}>
                                        {field.value}
                                    </Typography>
                                </Box>
                            </Box>
                        </Card>
                    </Grid>
                ))}
            </Grid>
        </Box>
    );
};

const RelatedItemsTab: React.FC<{ 
    assetId: string;
    relatedVersionsData: RelatedVersionsResponse | undefined;
    isLoading: boolean;
    onLoadMore: () => void;
}> = ({ assetId, relatedVersionsData, isLoading, onLoadMore }) => {
    const items = useMemo(() => {
        if (!relatedVersionsData?.data?.hits) return [];
        return relatedVersionsData.data.hits.map((hit) => ({
            id: hit.InventoryID,
            title: hit.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name,
            type: hit.DigitalSourceAsset.Type.toLowerCase(),
            thumbnail: hit.thumbnailUrl || hit.proxyUrl,
            score: hit.score,
            format: hit.DigitalSourceAsset.MainRepresentation.Format,
            fileSize: hit.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size,
            createDate: hit.DigitalSourceAsset.CreateDate
        }));
    }, [relatedVersionsData]);

    const hasMore = useMemo(() => {
        if (!relatedVersionsData?.data) return false;
        return relatedVersionsData.data.totalResults > relatedVersionsData.data.page * relatedVersionsData.data.pageSize;
    }, [relatedVersionsData]);

    return (
        <RelatedItemsView
            items={items}
            isLoading={isLoading}
            onLoadMore={onLoadMore}
            hasMore={hasMore}
        />
    );
};

const VideoDetailContent: React.FC = () => {
    const videoViewerRef = useRef<VideoViewerRef>(null);
    console.log("Parent videoViewerRef:", videoViewerRef); // Debug log
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const location = useLocation();
    const { isExpanded } = useRightSidebar();
    const { data: assetData, isLoading, error } = useAsset(id || '') as { data: AssetResponse | undefined; isLoading: boolean; error: any };
    const [activeTab, setActiveTab] = useState<string>('summary');

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
                { label: 'Date Created', value: '2024-01-07' }
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
        const now = new Date().toISOString();
        const formattedTimestamp = formatLocalDateTime(now, { showSeconds: true });

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

    // Handle keyboard navigation for tabs
    const handleTabKeyDown = useCallback((event: React.KeyboardEvent) => {
        const tabs = ['summary', 'technical', 'descriptor', 'related'];
        const currentIndex = tabs.indexOf(activeTab);
        
        if (event.key === 'ArrowRight') {
            const nextIndex = (currentIndex + 1) % tabs.length;
            setActiveTab(tabs[nextIndex]);
        } else if (event.key === 'ArrowLeft') {
            const prevIndex = (currentIndex - 1 + tabs.length) % tabs.length;
            setActiveTab(tabs[prevIndex]);
        }
    }, [activeTab]);

    const handleBack = useCallback(() => {
        // If we came from a specific location with state, go back to that location
        if (location.state && (location.state.searchTerm || location.state.preserveSearch)) {
            navigate(-1);
        } else {
            // Fallback to search page with search term if available
            navigate(`/search${searchTerm ? `?q=${encodeURIComponent(searchTerm)}` : ''}`);
        }
    }, [navigate, location.state, searchTerm]);

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
                    onBack={handleBack}
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
            bgcolor: 'transparent',
        }}>
            <Box sx={{ position: 'sticky', top: 0, zIndex: 1200, background: 'transparent' }}>
                <Box sx={{ py: 0, mb: 0 }}>
                    <BreadcrumbNavigation
                        searchTerm={searchTerm}
                        currentResult={48}
                        totalResults={156}
                        onBack={handleBack}
                        onPrevious={() => navigate(-1)}
                        onNext={() => navigate(1)}
                        assetName={assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name}
                        assetId={assetData.data.asset.InventoryID}
                        assetType="Video"
                    />
                </Box>
            </Box>

            <Box sx={{ px: 3, pt: 0, pb: 0, mt: 0, mb: 0 }}>
                <AssetHeader />
            </Box>

            <Box sx={{ px: 3, pt: 0, pb: 0, mt: 0, height: 'calc(100vh - 200px)', display: 'flex', flexDirection: 'column' }}>
                <Paper
                    elevation={0}
                    sx={{
                        overflow: 'hidden',
                        borderRadius: 2,
                        background: 'transparent',
                        position: 'relative',
                        height: '100%'
                    }}
                >
                    <AssetVideo
                        ref={videoViewerRef}
                        src={proxyUrl}
                        alt={assetData.data.asset.DigitalSourceAsset.MainRepresentation.ID}
                    />
                </Paper>
            </Box>

            <Box sx={{ px: 3, pb: 3 }}>
                <Box sx={{ mt: 1 }}>
                    <Paper
                        elevation={0}
                        sx={{
                            p: 0,
                            borderRadius: 2,
                            overflow: 'hidden',
                            background: 'transparent'
                        }}
                    >
                        <Tabs
                            value={activeTab}
                            onChange={(e, newValue) => setActiveTab(newValue)}
                            onKeyDown={handleTabKeyDown}
                            textColor="secondary"
                            indicatorColor="secondary"
                            aria-label="metadata tabs"
                            sx={{
                                px: 2,
                                pt: 1,
                                '& .MuiTab-root': {
                                    minWidth: 'auto',
                                    px: 2,
                                    py: 1.5,
                                    fontWeight: 500,
                                    transition: 'all 0.2s',
                                    '&:hover': {
                                        backgroundColor: theme => alpha(theme.palette.secondary.main, 0.05)
                                    }
                                }
                            }}
                        >
                            <Tab
                                value="summary"
                                label="Summary"
                                id="tab-summary"
                                aria-controls="tabpanel-summary"
                            />
                            <Tab
                                value="technical"
                                label="Technical Metadata"
                                id="tab-technical"
                                aria-controls="tabpanel-technical"
                            />
                            <Tab
                                value="descriptor"
                                label="Descriptor Metadata"
                                id="tab-descriptor"
                                aria-controls="tabpanel-descriptor"
                            />
                            <Tab
                                value="related"
                                label="Related Items"
                                id="tab-related"
                                aria-controls="tabpanel-related"
                            />
                        </Tabs>
                        <Box
                            sx={{
                                mt: 3,
                                mx: 3,
                                mb: 3,
                                pt: 2,
                                outline: 'none', // Remove outline when focused but keep it accessible
                                borderRadius: 1,
                                backgroundColor: theme => alpha(theme.palette.background.paper, 0.5)
                            }}
                            role="tabpanel"
                            id={`tabpanel-${activeTab}`}
                            aria-labelledby={`tab-${activeTab}`}
                            tabIndex={0} // Make the panel focusable
                        >
                            {activeTab === 'summary' && <SummaryTab metadataFields={metadataFields} />}
                            {activeTab === 'technical' && <TechnicalMetadataTab metadataAccordions={metadataAccordions} />}
                            {activeTab === 'descriptor' && <DescriptorMetadataTab metadataFields={metadataFields} />}
                            {activeTab === 'related' && (
                                <RelatedItemsTab 
                                    assetId={id || ''} 
                                    relatedVersionsData={assetData?.data?.asset?.relatedVersionsData} 
                                    isLoading={isLoading} 
                                    onLoadMore={() => {}} 
                                />
                            )}
                        </Box>
                    </Paper>
                </Box>
            </Box>

            <AssetSidebar
                versions={versions}
                comments={comments}
                onAddComment={handleAddComment}
                videoViewerRef={videoViewerRef}      
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
