import React, { useState, useMemo, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { Box, CircularProgress, Typography, List, ListItem, Paper, Button, Divider, Tabs, Tab } from '@mui/material';
import { useAsset } from '../api/hooks/useAssets';
import { RightSidebarProvider, useRightSidebar } from '../components/common/RightSidebar';
import { RecentlyViewedProvider, useTrackRecentlyViewed } from '../contexts/RecentlyViewedContext';
import { formatCamelCase } from '../utils/stringUtils';
import { TruncatedTextWithTooltip } from '../components/common/TruncatedTextWithTooltip';
import { formatFileSize } from '../utils/imageUtils';
import { formatLocalDateTime } from '@/shared/utils/dateUtils';
import ImageViewer from '../components/common/ImageViewer';
import BreadcrumbNavigation from '../components/common/BreadcrumbNavigation';
import AssetSidebar from '../components/asset/AssetSidebar';
import CommentPopper from '../components/common/CommentPopper';
import MetadataSection from '../components/common/MetadataSection';
import { SimpleTreeView } from '@mui/x-tree-view/SimpleTreeView';
import { TreeItem } from '@mui/x-tree-view/TreeItem';

// MUI Icons
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';

const categoryMapping = {
    exif: 'EXIF',
    ifd1: 'Thumbnail (IFD1)',
    ifd0: 'Image (IFD0)',
    gps: 'GPS',
    iptc: 'IPTC',
    xmp: 'XMP',
    icc: 'ICC',
    jfif: 'JFIF (JPEG only)',
    ihdr: 'IHDR (PNG only)',
    makerNote: 'Maker Note',
    userComment: 'User Comment',
    xmpRights: 'Rights',
    Iptc4xmpCore: 'IPTC Core',
    Iptc4xmpExt: 'IPTC Extension',
    photoshop: 'Photoshop',
    plus: 'PLUS',
    dc: 'Dublin Core',
    xmpMM: 'XMP Media Management',
    aux: 'Auxiliary',
    crs: 'Camera Raw Settings',
    exifEX: 'EXIF Extended',
    xmpDM: 'XMP Dynamic Media',
    interop: 'Interoperability'
};

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

// Tab content components
const SummaryTab: React.FC<{ assetData: any }> = ({ assetData }) => {
    // Create summary data from asset data
    const summaryData = [
        { label: 'Title', value: assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.ObjectKey?.Name || 'Unknown' },
        { label: 'Type', value: assetData?.data?.asset?.DigitalSourceAsset?.Type || 'Image' },
        { label: 'Size', value: formatFileSize(assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.FileInfo?.Size) },
        { label: 'Format', value: assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.Format || 'Unknown' },
        { label: 'Created Date', value: assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.FileInfo?.LastModified || 'Unknown' }
    ];

    // Add dimensions if available
    const resolution = assetData?.data?.asset?.DerivedRepresentations?.find(rep => rep.ImageSpec?.Resolution)?.ImageSpec?.Resolution;
    if (resolution) {
        summaryData.push({ label: 'Dimensions', value: `${resolution.Width}x${resolution.Height}` });
    }

    return (
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 2 }}>
            {summaryData.map((field, index) => (
                <Box key={index}>
                    <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                        {field.label}:
                    </Typography>
                    <Typography variant="body2">{field.value}</Typography>
                </Box>
            ))}
        </Box>
    );
};

const TechnicalMetadataTab: React.FC<{ metadataAccordions: any[] }> = ({ metadataAccordions }) => {
    return (
        <Box>
            <SimpleTreeView
                sx={{ flexGrow: 1, overflowY: 'auto' }}
                slots={{
                    collapseIcon: ExpandMoreIcon,
                    expandIcon: ChevronRightIcon
                }}
            >
                {metadataAccordions.map((parentAccordion, parentIndex) => (
                    <TreeItem
                        key={parentIndex}
                        itemId={`parent-${parentIndex}`}
                        label={`${parentAccordion.category} (${parentAccordion.count})`}
                    >
                        {parentAccordion.subCategories.map((subCategory, subIndex) => (
                            <TreeItem
                                key={`${parentIndex}-${subIndex}`}
                                itemId={`${parentIndex}-${subIndex}`}
                                label={`${subCategory.category} (${subCategory.count})`}
                            >
                                <Box sx={{ p: 2 }}>
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

const DescriptorMetadataTab: React.FC<{ assetData: any }> = ({ assetData }) => {
    // This would typically contain descriptive metadata like who/what is in the image
    // For now, we'll use placeholder data
    const descriptiveData = [
        { label: 'Description', value: 'High-resolution image from the collection' },
        { label: 'Keywords', value: 'nature, landscape, photography' },
        { label: 'Location', value: 'Unknown' },
        { label: 'People', value: 'None identified' },
        { label: 'Objects', value: 'Various natural elements' }
    ];

    return (
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 2 }}>
            {descriptiveData.map((field, index) => (
                <Box key={index}>
                    <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                        {field.label}:
                    </Typography>
                    <Typography variant="body2">{field.value}</Typography>
                </Box>
            ))}
        </Box>
    );
};

const RelatedItemsTab: React.FC = () => {
    // This would typically fetch related items from an API
    // For now, we'll use placeholder data
    const relatedItems = [
        { id: '1', title: 'Related Image 1', type: 'image', thumbnail: 'https://example.com/thumb1.jpg' },
        { id: '2', title: 'Related Video 1', type: 'video', thumbnail: 'https://example.com/thumb2.jpg' },
        { id: '3', title: 'Related Audio 1', type: 'audio', thumbnail: 'https://example.com/thumb3.jpg' },
    ];

    return (
        <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 2 }}>
            {relatedItems.map((item) => (
                <Paper key={item.id} elevation={2} sx={{ p: 2 }}>
                    <Typography variant="subtitle1">{item.title}</Typography>
                    <Typography variant="body2">Type: {item.type}</Typography>
                </Paper>
            ))}
        </Box>
    );
};

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

const ImageDetailContent: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const { data: assetData, isLoading, error } = useAsset(id || '');
    const navigate = useNavigate();
    const location = useLocation();
    const { isExpanded } = useRightSidebar();
    const [expandedMetadata, setExpandedMetadata] = useState<{ [key: string]: boolean }>({});
    const [commentAnchorEl, setCommentAnchorEl] = useState<null | HTMLElement>(null);
    const [selectedComment, setSelectedComment] = useState<number | null>(null);
    const [newComment, setNewComment] = useState('');
    const [activeTab, setActiveTab] = useState<string>('summary');

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
    const [comments, setComments] = useState([
        { user: "John Doe", avatar: "https://mui.com/static/images/avatar/1.jpg", content: "Great composition!", timestamp: "2023-06-15 09:30:22" },
        { user: "Jane Smith", avatar: "https://mui.com/static/images/avatar/2.jpg", content: "The lighting is perfect", timestamp: "2023-06-15 10:15:43" },
        { user: "Mike Johnson", avatar: "https://mui.com/static/images/avatar/3.jpg", content: "Can we adjust the contrast?", timestamp: "2023-06-15 11:22:17" },
    ]);

    // Get all the search state from location.state
    const {
        searchTerm = '',
        page = 1,
        viewMode = 'card',
        cardSize = 'medium',
        aspectRatio = 'square',
        thumbnailScale = 'fit',
        showMetadata = true,
        groupByType = false,
        filters = {},
        sorting = [],
        isSemantic = false,
        currentResult = 1,
        totalResults = 0
    } = location.state || {};

    const handleCommentClick = useCallback((event: React.MouseEvent<HTMLElement>, index: number) => {
        setCommentAnchorEl(commentAnchorEl && selectedComment === index ? null : event.currentTarget);
        setSelectedComment(selectedComment === index ? null : index);
    }, [commentAnchorEl, selectedComment]);

    const handleCommentSubmit = useCallback(() => {
        if (newComment.trim()) {
            const now = new Date().toISOString();
            const formattedTimestamp = formatLocalDateTime(now, { showSeconds: true });

            const newCommentObj = {
                user: "Current User",
                avatar: "https://mui.com/static/images/avatar/1.jpg",
                content: newComment,
                timestamp: formattedTimestamp
            };
            setComments(prevComments => [...prevComments, newCommentObj]);
            setNewComment('');
        }
    }, [newComment]);

    const toggleMetadataExpansion = useCallback((key: string) => {
        setExpandedMetadata(prev => ({ ...prev, [key]: !prev[key] }));
    }, []);

    const transformMetadata = useCallback((metadata: any) => {
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
    }, []);

    const metadataAccordions = useMemo(() => {
        if (!assetData?.data?.asset?.Metadata) return [];
        return transformMetadata(assetData.data.asset.Metadata);
    }, [assetData, transformMetadata]);

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
                type: rep.Purpose,
                format: rep.Format,
                fileSize: formatFileSize(rep.StorageInfo.PrimaryLocation.FileInfo.Size),
                description: `${rep.Format} file - ${formatFileSize(rep.StorageInfo.PrimaryLocation.FileInfo.Size)}${rep.ImageSpec?.Resolution ? ` - ${rep.ImageSpec.Resolution.Width}x${rep.ImageSpec.Resolution.Height}` : ''}`

            }))
        ];
    }, [assetData]);

    const proxyUrl = useMemo(() => {
        if (!assetData?.data?.asset) return '';
        const proxyRep = assetData.data.asset.DerivedRepresentations.find(rep => rep.Purpose === 'proxy');
        return proxyRep?.URL || assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.FullPath;
    }, [assetData]);

    useTrackRecentlyViewed(
        useMemo(() => {
            if (!assetData?.data?.asset) return null;
            return {
                id: assetData.data.asset.DigitalSourceAsset.MainRepresentation.ID,
                title: assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name,
                type: assetData.data.asset.DigitalSourceAsset.Type.toLowerCase() as "image" | "video",
                path: `/${assetData.data.asset.DigitalSourceAsset.Type.toLowerCase()}s/${assetData.data.asset.InventoryID}`,
                searchTerm: searchTerm,
                metadata: {
                    fileSize: formatFileSize(assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size),
                    dimensions: assetData.data.asset.DerivedRepresentations.find(rep => rep.ImageSpec?.Resolution)?.ImageSpec?.Resolution
                        ? `${assetData.data.asset.DerivedRepresentations.find(rep => rep.ImageSpec?.Resolution)?.ImageSpec?.Resolution.Width}x${assetData.data.asset.DerivedRepresentations.find(rep => rep.ImageSpec?.Resolution)?.ImageSpec?.Resolution.Height}`
                        : undefined
                }
            };
        }, [assetData, searchTerm])
    );

    const handleBack = useCallback(() => {
        // Construct query parameters
        const queryParams = new URLSearchParams();
        if (searchTerm) {
            queryParams.set('q', searchTerm);
        }
        if (page > 1) {
            queryParams.set('page', page.toString());
        }
        if (isSemantic) {
            queryParams.set('semantic', 'true');
        }

        // Navigate back to search with all state preserved
        const previousPath = location.pathname;
        navigate({
            pathname: previousPath,
            search: queryParams.toString(),
            state: {
                preserveSearch: true,
                searchTerm,
                page,
                viewMode,
                cardSize,
                aspectRatio,
                thumbnailScale,
                showMetadata,
                groupByType,
                filters,
                sorting,
                isSemantic,
                currentResult,
                totalResults
            }
        } as any); // Type assertion needed due to React Router types
    }, [
        navigate,
        searchTerm,
        page,
        viewMode,
        cardSize,
        aspectRatio,
        thumbnailScale,
        showMetadata,
        groupByType,
        filters,
        sorting,
        isSemantic,
        currentResult,
        totalResults,
        location.pathname
    ]);

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
                <Typography variant="h5" color="error">Error loading asset data</Typography>
                <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)} sx={{ mt: 2 }}>
                    Go Back
                </Button>
            </Box>
        );
    }

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
            <Box sx={{
                position: 'sticky',
                top: 0,
                zIndex: 1200
            }}>
                <Box sx={{ px: 3, py: 2 }}>
                    <BreadcrumbNavigation
                        searchTerm={searchTerm}
                        currentResult={currentResult}
                        totalResults={totalResults}
                        onBack={handleBack}
                        assetName={assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name}
                        assetId={assetData.data.asset.InventoryID}
                        assetType="Image"
                    />
                </Box>
            </Box>

            <Box sx={{
                display: 'flex',
                flexDirection: 'column',
                flex: 1,
                overflow: 'auto',
                gap: 3,
                px: 3,
                pb: 3,
                mt: 2
            }}>
                <Box sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 3
                }}>
                    <Box sx={{
                        position: 'relative',
                        bgcolor: 'background.default',
                        pt: 2
                    }}>
                        <ImageViewer imageSrc={proxyUrl} maxHeight={600} />
                    </Box>

                    <Box>
                        <Paper elevation={3} sx={{ p: 2 }}>
                            <Tabs
                                value={activeTab}
                                onChange={(e, newValue) => setActiveTab(newValue)}
                                onKeyDown={handleTabKeyDown}
                                textColor="secondary"
                                indicatorColor="secondary"
                                aria-label="metadata tabs"
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
                                    pt: 2,
                                    outline: 'none' // Remove outline when focused but keep it accessible
                                }}
                                role="tabpanel"
                                id={`tabpanel-${activeTab}`}
                                aria-labelledby={`tab-${activeTab}`}
                                tabIndex={0} // Make the panel focusable
                            >
                                {activeTab === 'summary' && <SummaryTab assetData={assetData} />}
                                {activeTab === 'technical' && <TechnicalMetadataTab metadataAccordions={metadataAccordions} />}
                                {activeTab === 'descriptor' && <DescriptorMetadataTab assetData={assetData} />}
                                {activeTab === 'related' && <RelatedItemsTab />}
                            </Box>
                        </Paper>
                    </Box>
                </Box>


                <AssetSidebar
                    versions={versions}
                // comments={comments}
                // onAddComment={handleAddComment}
                />

                {selectedComment !== null && (
                    <CommentPopper
                        id={Boolean(commentAnchorEl) ? 'comment-popper' : undefined}
                        open={Boolean(commentAnchorEl)}
                        anchorEl={commentAnchorEl}
                        comment={comments[selectedComment]}
                        onClose={() => {
                            setCommentAnchorEl(null);
                            setSelectedComment(null);
                        }}
                    />
                )}
            </Box>
        </Box>
    );
};

const ImageDetailPage: React.FC = () => {
    return (
        <RecentlyViewedProvider>
            <RightSidebarProvider>
                <ImageDetailContent />
            </RightSidebarProvider>
        </RecentlyViewedProvider>
    );
};

export default ImageDetailPage;
