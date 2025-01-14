import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useMediaQuery, Theme } from '@mui/material';
import { Box, CircularProgress, Typography, Grid, List, ListItem, ListItemText, ListItemAvatar, Chip, Avatar, Paper, Button, Divider, IconButton, Stack, TextField } from '@mui/material';
import { styled, alpha } from '@mui/material/styles';
import { useAsset } from '../api/hooks/useAssets';
import { RightSidebarProvider, useRightSidebar } from '../components/common/RightSidebar';
import { RecentlyViewedProvider, useTrackRecentlyViewed } from '../contexts/RecentlyViewedContext';
import { formatCamelCase } from '../utils/stringUtils';
import { TruncatedTextWithTooltip } from '../components/common/TruncatedTextWithTooltip';
import { handleImageDownload, formatFileSize } from '../utils/imageUtils';
import ImageViewer from '../components/common/ImageViewer';
import BreadcrumbNavigation from '../components/common/BreadcrumbNavigation';
import AssetHeader from '../components/asset/AssetHeader';
import AssetSidebar from '../components/asset/AssetSidebar';
import CommentPopper from '../components/common/CommentPopper';

// MUI Icons
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import ColorLensIcon from '@mui/icons-material/ColorLens';
import BackupIcon from '@mui/icons-material/Backup';
import DescriptionIcon from '@mui/icons-material/Description';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';

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

const ImageDetailContent: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const { data: assetData, isLoading, error } = useAsset(id || '');
    const navigate = useNavigate();
    const location = useLocation();
    const searchParams = new URLSearchParams(location.search);
    const searchTerm = searchParams.get('searchTerm') || '';
    const { isExpanded } = useRightSidebar();
    const [expandedMetadata, setExpandedMetadata] = useState<{ [key: string]: boolean }>({});
    const [commentAnchorEl, setCommentAnchorEl] = useState<null | HTMLElement>(null);
    const [selectedComment, setSelectedComment] = useState<number | null>(null);
    const [newComment, setNewComment] = useState('');
    const [comments, setComments] = useState([
        { user: "John Doe", avatar: "https://mui.com/static/images/avatar/1.jpg", content: "Great composition!", timestamp: "2023-06-15 09:30:22" },
        { user: "Jane Smith", avatar: "https://mui.com/static/images/avatar/2.jpg", content: "The lighting is perfect", timestamp: "2023-06-15 10:15:43" },
        { user: "Mike Johnson", avatar: "https://mui.com/static/images/avatar/3.jpg", content: "Can we adjust the contrast?", timestamp: "2023-06-15 11:22:17" },
    ]);

    const handleCommentClick = (event: React.MouseEvent<HTMLElement>, index: number) => {
        setCommentAnchorEl(commentAnchorEl && selectedComment === index ? null : event.currentTarget);
        setSelectedComment(selectedComment === index ? null : index);
    };

    const handleCommentSubmit = () => {
        if (newComment.trim()) {
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

            const newCommentObj = {
                user: "Current User",
                avatar: "https://mui.com/static/images/avatar/1.jpg",
                content: newComment,
                timestamp: formattedTimestamp
            };
            setComments([...comments, newCommentObj]);
            setNewComment('');
        }
    };

    const toggleMetadataExpansion = (key: string) => {
        setExpandedMetadata(prev => ({ ...prev, [key]: !prev[key] }));
    };

    const metadataAccordions = useMemo(() => {
        if (!assetData?.data?.asset?.Metadata) return [];
        return transformMetadata(assetData.data.asset.Metadata);
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

    useTrackRecentlyViewed(
        assetData ? {
            id: assetData.data.asset.DigitalSourceAsset.MainRepresentation.ID,
            title: assetData.data.asset.DigitalSourceAsset.MainRepresentation.ID,
            type: assetData.data.asset.DigitalSourceAsset.Type.toLowerCase() as "image" | "video",
            path: `/assets/${id}`,
            metadata: {
                fileSize: formatFileSize(assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size),
                dimensions: assetData.data.asset.DerivedRepresentations.find(rep => rep.ImageSpec?.Resolution)?.ImageSpec?.Resolution
                    ? `${assetData.data.asset.DerivedRepresentations.find(rep => rep.ImageSpec?.Resolution)?.ImageSpec?.Resolution.Width}x${assetData.data.asset.DerivedRepresentations.find(rep => rep.ImageSpec?.Resolution)?.ImageSpec?.Resolution.Height}`
                    : undefined
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
                <Typography variant="h5" color="error">Error loading asset data</Typography>
                <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)} sx={{ mt: 2 }}>
                    Go Back
                </Button>
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
            <BreadcrumbNavigation
                searchTerm={searchTerm}
                currentResult={48}
                totalResults={156}
                onBack={() => navigate(-1)}
                onPrevious={() => navigate(-1)}
                onNext={() => navigate(1)}
            />

            <Box sx={{ px: 3, pt: 2, bgcolor: 'background.default' }}>
                <AssetHeader />
            </Box>

            <Box sx={{
                display: 'flex',
                flexDirection: 'column',
                flex: 1,
                overflow: 'auto',
                gap: 3,
                px: 3,
                pb: 3
            }}>
                <Box sx={{
                    position: 'sticky',
                    top: 120,
                    zIndex: 1100,
                    bgcolor: 'background.default',
                    pt: 2
                }}>
                    <ImageViewer imageSrc={proxyUrl} maxHeight={600} />
                </Box>

                <Box sx={{ flex: 1 }}>
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

            <AssetSidebar versions={assetData.data.asset.DerivedRepresentations.map(rep => ({
                id: rep.ID,
                src: rep.StorageInfo.PrimaryLocation.ObjectKey.FullPath,
                type: rep.Purpose,
                format: rep.Format,
                fileSize: formatFileSize(rep.StorageInfo.PrimaryLocation.FileInfo.Size),
                description: `${rep.Format} file - ${formatFileSize(rep.StorageInfo.PrimaryLocation.FileInfo.Size)}${rep.ImageSpec?.Resolution ? ` - ${rep.ImageSpec.Resolution.Width}x${rep.ImageSpec.Resolution.Height}` : ''
                    }`
            }))} />

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
