import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useMediaQuery, Theme } from '@mui/material';
import { green, red, yellow } from '@mui/material/colors';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
// MUI Components
import { formatCamelCase } from '../utils/stringUtils';
import { TruncatedTextWithTooltip } from '../components/common/TruncatedTextWithTooltip';
import {
    Box,
    Typography,
    Grid,
    List,
    ListItem,
    ListItemText,
    ListItemAvatar,
    Chip,
    Avatar,
    Paper,
    CircularProgress,
    Button,
    Divider,
    IconButton,
    Stack,
    TextField,
    Menu,
    MenuItem,
} from '@mui/material';
import { styled, alpha } from '@mui/material/styles';
import type { MenuProps } from '@mui/material/Menu';
import CommentPopper from '../components/common/CommentPopper';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import LocalOfferIcon from '@mui/icons-material/LocalOffer';

import ColorLensIcon from '@mui/icons-material/ColorLens';
import ThumbUpAltIcon from '@mui/icons-material/ThumbUpAlt';
import CloudDownloadIcon from '@mui/icons-material/CloudDownload';
import BackupIcon from '@mui/icons-material/Backup';
import PersonIcon from '@mui/icons-material/Person';
import FileIcon from '@mui/icons-material/InsertDriveFile';
import ImageIcon from '@mui/icons-material/Image';
import DescriptionIcon from '@mui/icons-material/Description';
import { handleImageDownload, formatFileSize } from '../utils/imageUtils';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
// MUI Icons
import ArrowBackIosSharpIcon from '@mui/icons-material/ArrowBackIosSharp';
import ArrowForwardIosSharpIcon from '@mui/icons-material/ArrowForwardIosSharp';
import MuiAccordion, { AccordionProps } from '@mui/material/Accordion';
import MuiAccordionSummary, {
    AccordionSummaryProps,
} from '@mui/material/AccordionSummary';
import MuiAccordionDetails from '@mui/material/AccordionDetails';
import EditIcon from '@mui/icons-material/Edit';
import ArchiveIcon from '@mui/icons-material/Archive';
import FileCopyIcon from '@mui/icons-material/FileCopy';
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline'; // Import the pipeline icon

// Custom components and hooks
import { ImageViewer } from '../components/common/ImageViewer';
import { useAsset } from '../api/hooks/useAssets';

const NestedMetadata: React.FC<{ data: any, isTopLevel?: boolean }> = ({ data, isTopLevel = false }) => {
    if (Array.isArray(data)) {
        return (
            <List dense disablePadding>
                {data.map((item, index) => (
                    <ListItem key={index} sx={{ pl: isTopLevel ? 0 : 2 }}>
                        <NestedMetadata data={item} />
                    </ListItem>
                ))}
            </List>
        );
    } else if (typeof data === 'object' && data !== null) {
        return (
            <List dense disablePadding>
                {Object.entries(data).map(([key, value]) => (
                    <ListItem key={key} sx={{ pl: isTopLevel ? 0 : 2, flexDirection: 'column', alignItems: 'flex-start' }}>
                        <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                            {formatCamelCase(key)}:
                        </Typography>
                        <Box sx={{ pl: 2, width: '100%' }}>
                            <NestedMetadata data={value} />
                        </Box>
                    </ListItem>
                ))}
            </List>
        );
    } else {
        return <Typography variant="body2">{String(data)}</Typography>;
    }
};

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




interface Pipeline {
    id: string;
    name: string;
    description: string;
    icon: string;
    estimatedTime: string;
}

interface BaseRepresentation {
    Format: string;
    ID: string;
    Purpose: string;
    StorageInfo: {
        PrimaryLocation: {
            Bucket: string;
            FileInfo: {
                Size: number;
            };
            ObjectKey: {
                FullPath: string;
            };
            Status: string;
            StorageType: string;
        };
    };
}

interface ImageRepresentation extends BaseRepresentation {
    Type: 'Image';
    ImageSpec?: {
        Resolution: {
            Width: string;
            Height: string;
        };
    };
    URL?: string;
}

interface OtherRepresentation extends BaseRepresentation {
    Type?: string;
    URL?: string;
}

type Representation = ImageRepresentation | OtherRepresentation;

function isImageRepresentation(rep: Representation): rep is ImageRepresentation {
    return rep.Type === 'Image';
}

const Accordion = styled((props: AccordionProps) => (
    <MuiAccordion disableGutters elevation={0} square {...props} />
))(({ theme }) => ({
    border: `1px solid ${theme.palette.divider}`,
    '&:not(:last-child)': {
        borderBottom: 0,
    },
    '&::before': {
        display: 'none',
    },
}));

const AccordionSummary = styled((props: AccordionSummaryProps) => (
    <MuiAccordionSummary
        expandIcon={<ArrowForwardIosSharpIcon sx={{ fontSize: '0.9rem' }} />}
        {...props}
    />
))(({ theme }) => ({
    backgroundColor: 'rgba(0, 0, 0, .03)',
    flexDirection: 'row-reverse',
    '& .MuiAccordionSummary-expandIconWrapper.Mui-expanded': {
        transform: 'rotate(90deg)',
    },
    '& .MuiAccordionSummary-content': {
        marginLeft: theme.spacing(1),
    },
    ...theme.applyStyles('dark', {
        backgroundColor: 'rgba(255, 255, 255, .05)',
    }),
}));

const AccordionDetails = styled(MuiAccordionDetails)(({ theme }) => ({
    padding: theme.spacing(2),
    borderTop: '1px solid rgba(0, 0, 0, .125)',
}));

const StyledMenu = styled((props: MenuProps) => (
    <Menu
        elevation={0}
        anchorOrigin={{
            vertical: 'bottom',
            horizontal: 'right',
        }}
        transformOrigin={{
            vertical: 'top',
            horizontal: 'right',
        }}
        {...props}
    />
))(({ theme }) => ({
    '& .MuiPaper-root': {
        borderRadius: 6,
        marginTop: theme.spacing(1),
        minWidth: 180,
        color: 'rgb(55, 65, 81)',
        boxShadow:
            'rgb(255, 255, 255) 0px 0px 0px 0px, rgba(0, 0, 0, 0.05) 0px 0px 0px 1px, rgba(0, 0, 0, 0.1) 0px 10px 15px -3px, rgba(0, 0, 0, 0.05) 0px 4px 6px -2px',
        '& .MuiMenu-list': {
            padding: '4px 0',
        },
        '& .MuiMenuItem-root': {
            '& .MuiSvgIcon-root': {
                fontSize: 18,
                color: theme.palette.text.secondary,
                marginRight: theme.spacing(1.5),
            },
            '&:active': {
                backgroundColor: alpha(
                    theme.palette.primary.main,
                    theme.palette.action.selectedOpacity,
                ),
            },
        },
        ...theme.applyStyles('dark', {
            color: theme.palette.grey[300],
        }),
    },
}));

const ImageDetailPage: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const { data: assetData, isLoading, error } = useAsset(id || '');
    const navigate = useNavigate();
    const [commentAnchorEl, setCommentAnchorEl] = React.useState<null | HTMLElement>(null);
    const [selectedComment, setSelectedComment] = React.useState<number | null>(null);
    const [newComment, setNewComment] = useState('');
    const handleCommentClick = (event: React.MouseEvent<HTMLElement>, index: number) => {
        setCommentAnchorEl(commentAnchorEl && selectedComment === index ? null : event.currentTarget);
        setSelectedComment(selectedComment === index ? null : index);
    };

    const commentOpen = Boolean(commentAnchorEl);
    const commentPopperId = commentOpen ? 'comment-popper' : undefined;

    const [expandedMetadata, setExpandedMetadata] = useState<{ [key: string]: boolean }>({});

    const toggleMetadataExpansion = (key: string) => {
        setExpandedMetadata(prev => ({ ...prev, [key]: !prev[key] }));
    };

    const isLargeScreen = useMediaQuery('(min-width:1200px)');

    const [expandedAccordions, setExpandedAccordions] = useState<{ [key: string]: boolean }>({});
    const handleClickOutside = useCallback((event: MouseEvent) => {
        if (commentAnchorEl && !commentAnchorEl.contains(event.target as Node)) {
            setCommentAnchorEl(null);
            setSelectedComment(null);
        }
    }, [commentAnchorEl]);

    useEffect(() => {
        document.addEventListener('mousedown', handleClickOutside);
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [handleClickOutside]);

    const getStatusColor = (status: string) => {
        switch (status.toLowerCase()) {
            case 'active':
                return green[500];
            case 'inactive':
                return red[500];
            default:
                return yellow[500];
        }
    };
    const getStatusInfo = () => {
        if (assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation) {
            const primaryLocation = assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation;
            return {
                status: primaryLocation.Status,
                name: primaryLocation.ObjectKey.Name
            };
        }
        return { status: 'unknown', name: 'Unknown' };
    };
    const { status, name } = getStatusInfo();
    const statusColor = getStatusColor(status);

    const representations = useMemo(() => {
        if (!assetData?.data?.asset) return [];

        const source: Representation = assetData.data.asset.DigitalSourceAsset.MainRepresentation;
        const derived: Representation[] = assetData.data.asset.DerivedRepresentations || [];

        return [
            {
                type: 'Source',
                data: source,
                icon: <FileIcon />,
            },
            ...derived.map(rep => ({
                type: rep.Purpose,
                data: rep,
                icon: rep.Type === 'Image' ? <ImageIcon /> : <DescriptionIcon />,
            }))
        ];
    }, [assetData]);

    const handleAccordionChange = (accordionId: string) => (event: React.SyntheticEvent, isExpanded: boolean) => {
        setExpandedAccordions(prev => ({
            ...prev,
            [accordionId]: isExpanded
        }));
    };
    const [comments, setComments] = useState([
        { user: "John Doe", avatar: "https://mui.com/static/images/avatar/1.jpg", content: "Great composition!", timestamp: "2023-06-15 09:30:22" },
        { user: "Jane Smith", avatar: "https://mui.com/static/images/avatar/2.jpg", content: "The lighting is perfect", timestamp: "2023-06-15 10:15:43" },
        { user: "Mike Johnson", avatar: "https://mui.com/static/images/avatar/3.jpg", content: "Can we adjust the contrast?", timestamp: "2023-06-15 11:22:17" },
        { user: "Sarah Brown", avatar: "https://mui.com/static/images/avatar/4.jpg", content: "Love the color palette", timestamp: "2023-06-15 13:45:09" },
        { user: "Tom Wilson", avatar: "https://mui.com/static/images/avatar/5.jpg", content: "Excellent product shot", timestamp: "2023-06-15 14:30:00" },
    ]);
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
                user: "Current User", // Replace with actual user name
                avatar: "https://mui.com/static/images/avatar/1.jpg", // Replace with actual user avatar
                content: newComment,
                timestamp: formattedTimestamp
            };
            setComments([...comments, newCommentObj]);
            setNewComment('');
        }
    };
    // const transformMetadata = (metadata: any) => {
    //     if (!metadata) return [];

    //     return Object.entries(metadata).map(([parentCategory, parentData]) => ({
    //         category: parentCategory,
    //         subCategories: Object.entries(parentData as Record<string, any>).map(([category, data]) => ({
    //             category,
    //             data: Object.entries(data as Record<string, string>).map(([key, value]) => ({ key, value })),
    //             count: Object.keys(data as Record<string, string>).length
    //         })),
    //         count: Object.keys(parentData as Record<string, any>).length
    //     }));
    // };
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

    const [derivedRepresentations] = useState(() => {
        if (!assetData?.data) return [];
        return [
            {
                id: assetData.data.asset.DigitalSourceAsset.MainRepresentation.ID,
                src: assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.FullPath,
                type: 'Original',
                description: 'Original high resolution version',
            },
            ...assetData.data.asset.DerivedRepresentations.map(rep => ({
                id: rep.ID,
                src: rep.StorageInfo.PrimaryLocation.ObjectKey.FullPath,
                type: rep.Purpose.charAt(0).toUpperCase() + rep.Purpose.slice(1),
                description: `${rep.Purpose} version`,
            }))
        ];
    });
    const [availablePipelines] = useState([
        { id: 'p1', name: 'Image Enhancement', description: 'Enhance image quality and colors', icon: ':art:', estimatedTime: '2-3 minutes' },
        { id: 'p2', name: 'Object Detection', description: 'Detect and label objects in the image', icon: ':mag:', estimatedTime: '1-2 minutes' }
    ]);
    const handlePipelineExecution = (pipelineId: string) => {
        console.log(`Executing pipeline: ${pipelineId}`);
    };

    const [anchorEl, setAnchorEl] = React.useState<null | HTMLElement>(null);
    const open = Boolean(anchorEl);
    const handleClick = (event: React.MouseEvent<HTMLElement>) => {
        setAnchorEl(event.currentTarget);
    };
    const handleClose = () => {
        setAnchorEl(null);
    };

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
                <Typography variant="h5" color="error">
                    {error ? 'Error loading asset details' : 'Asset not found'}
                </Typography>
                <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)} sx={{ mt: 2 }}>
                    Go Back
                </Button>
            </Box>
        );
    }
    // const getProxyUrl = () => {
    //     if (assetData?.data?.asset?.DerivedRepresentations) {
    //         const proxyRep = assetData.data.asset.DerivedRepresentations.find(rep => rep.Purpose === 'proxy');
    //         if (proxyRep) {
    //             return proxyRep.URL;
    //         }
    //     }
    //     return assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.ObjectKey?.Path;
    // };

    const getProxyUrl = () => {
        const proxyRep = assetData.data.asset.DerivedRepresentations.find(rep => rep.Purpose === 'proxy');
        return proxyRep?.URL || assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.FullPath;
    };
    const proxyUrl = getProxyUrl();
    return (
        <Box sx={{ flexGrow: 1, p: 3, maxWidth: '1600px', margin: '0 auto' }}>
            <Button startIcon={<ArrowBackIcon />} onClick={() => navigate(-1)} sx={{ mb: 3 }}>
                Back to Search Results
            </Button>
            <Grid container spacing={3} sx={{ flexGrow: 1 }}>
                {/* Left Panel - Inventory/Manifestation */}
                {isLargeScreen && (
                    <Grid item xs={2} sx={{ display: 'flex', flexDirection: 'column' }}>
                        <Paper elevation={3} sx={{ p: 2, display: 'flex', flexDirection: 'column', height: '100%' }}>
                            <Typography variant="h6" noWrap gutterBottom>Representations</Typography>
                            {representations.map((rep, index) => (
                                <Accordion key={index}>
                                    <AccordionSummary
                                        // expandIcon={<ExpandMoreIcon />}
                                        sx={{
                                            '& .MuiAccordionSummary-content': {
                                                overflow: 'hidden',
                                                flex: '1 1 auto',
                                            }
                                        }}
                                    >
                                        <Stack
                                            direction="row"
                                            spacing={1}
                                            alignItems="center"
                                            sx={{
                                                width: '100%',
                                                minWidth: 0  // This is crucial for text truncation
                                            }}
                                        >
                                            {rep.icon}
                                            <TruncatedTextWithTooltip text={rep.type.charAt(0).toUpperCase() + rep.type.slice(1)} />

                                        </Stack>
                                    </AccordionSummary>
                                    <AccordionDetails>
                                        <Stack spacing={1}>
                                            <Stack direction="row" spacing={1}>
                                                <Typography variant='body2'><strong>ID:</strong></Typography>
                                                <TruncatedTextWithTooltip text={`${rep.data.ID}`} />
                                            </Stack>
                                            <Stack direction="row" spacing={1}>
                                                <Typography variant='body2'><strong>Size:</strong></Typography>
                                                <TruncatedTextWithTooltip text={`${formatFileSize(rep.data.StorageInfo?.PrimaryLocation?.FileInfo?.Size || 0)}`} />
                                            </Stack>
                                            <Stack direction="row" spacing={1}>
                                                <Typography variant='body2'><strong>File Type:</strong></Typography>
                                                <TruncatedTextWithTooltip text={`${rep.data.Format || 'N/A'}`} />
                                            </Stack>

                                            {isImageRepresentation(rep.data) && rep.data.ImageSpec && (

                                                <Stack direction="row" spacing={1}>
                                                    <Typography variant='body2'><strong>Resolution:</strong></Typography>
                                                    <TruncatedTextWithTooltip text={`${rep.data.ImageSpec.Resolution.Width}x${rep.data.ImageSpec.Resolution.Height}`} />
                                                </Stack>
                                            )}
                                            {rep.data.URL && (
                                                <Button
                                                    variant="outlined"
                                                    size="small"
                                                    onClick={() => handleImageDownload(rep.data.URL, `${rep.type}_${rep.data.ID}.${rep.data.Format}`)}
                                                >
                                                    Download File
                                                </Button>
                                            )}
                                            {!rep.data.URL && rep.data.StorageInfo?.PrimaryLocation?.ObjectKey?.FullPath && (

                                                <Stack direction="row" spacing={1}>
                                                    <Typography variant='body2'><strong>File Path:</strong></Typography>
                                                    <TruncatedTextWithTooltip text={`${rep.data.StorageInfo.PrimaryLocation.ObjectKey.FullPath}`} />
                                                </Stack>
                                            )}
                                        </Stack>
                                    </AccordionDetails>
                                </Accordion>
                            ))}



                        </Paper>
                    </Grid>
                )}
                {/* Main Image Section with Status above */}
                <Grid item xs={isLargeScreen ? 8 : 12}>
                    {/* Status Section */}
                    <Paper elevation={3} sx={{ p: 2 }}>
                        <Stack direction="row" sx={{ justifyContent: "space-between", alignItems: "center" }}>
                            <Stack direction="row" spacing={2} alignItems="center">
                                <Box
                                    sx={{
                                        width: '20px',
                                        height: '20px',
                                        borderRadius: '50%',
                                        backgroundColor: statusColor,
                                    }}
                                />
                                <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center' }}>
                                    {name}
                                </Typography>
                            </Stack>
                            <div>
                                {!isLargeScreen ? (
                                    <IconButton
                                        aria-label="pipelines"
                                        onClick={handleClick}
                                        color="primary"
                                        size="large"
                                    >
                                        <AccountTreeIcon />
                                    </IconButton>
                                ) : (
                                    <Button
                                        id="pipeline-button"
                                        aria-controls={open ? 'pipeline-menu' : undefined}
                                        aria-haspopup="true"
                                        aria-expanded={open ? 'true' : undefined}
                                        variant="outlined"
                                        disableElevation
                                        onClick={handleClick}
                                        endIcon={<KeyboardArrowDownIcon />}
                                    >
                                        Pipelines
                                    </Button>
                                )}
                                <StyledMenu
                                    id="pipeline-menu"
                                    MenuListProps={{
                                        'aria-labelledby': 'pipeline-button',
                                    }}
                                    anchorEl={anchorEl}
                                    open={open}
                                    onClose={handleClose}
                                >
                                    {availablePipelines.map(pipeline => (


                                        <MenuItem key={pipeline.id} sx={{
                                            justifyContent: "space-between",
                                            alignItems: "baseline",
                                        }} disableRipple>
                                            {/* <EditIcon /> */}
                                            {pipeline.name}<Button onClick={() => handlePipelineExecution(pipeline.id)}>Run</Button>
                                        </MenuItem>
                                    ))}


                                </StyledMenu>
                            </div>

                        </Stack>
                    </Paper>
                    {/* Image Viewer */}
                    <Paper elevation={3} sx={{ p: 2, mt: 2, position: 'relative', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
                        <ImageViewer imageSrc={proxyUrl} maxHeight={600} />
                        {/* <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', position: 'absolute', top: '50%' }}>
                            <IconButton><ArrowBackIcon /></IconButton>
                            <IconButton><PlayArrowIcon /></IconButton>
                        </Box> */}
                    </Paper>
                </Grid>
                {/* Right Panel - Pipelines and Comments */}

                {isLargeScreen && (
                    <Grid item xs={2} sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                        <Paper elevation={3} sx={{ p: 2, display: 'flex', flexDirection: 'column', height: '100%', maxHeight: 'calc(100vh - 200px)' }}>
                            <Typography noWrap variant="h6" sx={{ mb: 2 }}>Comments</Typography>
                            <Box sx={{
                                display: 'flex',
                                flexDirection: 'column',
                                flexGrow: 1,
                                minHeight: 0,
                                overflow: 'hidden'
                            }}>
                                <Box sx={{
                                    flexGrow: 1,
                                    overflowY: 'auto',
                                    mb: 2,
                                    '&::-webkit-scrollbar': {
                                        width: '0.4em'
                                    },
                                    '&::-webkit-scrollbar-track': {
                                        boxShadow: 'inset 0 0 6px rgba(0,0,0,0.00)',
                                        webkitBoxShadow: 'inset 0 0 6px rgba(0,0,0,0.00)'
                                    },
                                    '&::-webkit-scrollbar-thumb': {
                                        backgroundColor: 'rgba(0,0,0,.1)',
                                        outline: '1px solid slategrey'
                                    }
                                }}>
                                    <Stack spacing={2}>
                                        {comments.map((comment, index) => (
                                            <Box
                                                key={index}
                                                sx={{
                                                    display: 'flex',
                                                    justifyContent: index % 2 === 0 ? 'flex-start' : 'flex-end',
                                                    width: '100%',
                                                }}
                                            >
                                                <Box
                                                    sx={{
                                                        display: 'flex',
                                                        flexDirection: index % 2 === 0 ? 'row' : 'row-reverse',
                                                        alignItems: 'center',
                                                        maxWidth: '80%',
                                                    }}
                                                >
                                                    <Avatar
                                                        src={comment.avatar}
                                                        sx={{
                                                            width: 32,
                                                            height: 32,
                                                            marginRight: index % 2 === 0 ? 1 : 0,
                                                            marginLeft: index % 2 === 0 ? 0 : 1,
                                                        }}
                                                    />
                                                    <Chip
                                                        label={comment.content}
                                                        onClick={(event) => handleCommentClick(event, index)}
                                                        variant="outlined"
                                                        color={index % 2 === 0 ? "primary" : "success"}
                                                        sx={{
                                                            height: 'auto',
                                                            '& .MuiChip-label': {
                                                                display: 'block',
                                                                whiteSpace: 'normal',
                                                                padding: '8px 12px',
                                                            },
                                                        }}
                                                    />
                                                </Box>
                                            </Box>
                                        ))}
                                    </Stack>
                                </Box>
                            </Box>
                            <Box sx={{ mt: 'auto' }}>
                                <Box sx={{ display: 'flex', alignItems: 'flex-end' }}>
                                    <TextField
                                        multiline
                                        fullWidth
                                        rows={2}
                                        maxRows={4}
                                        placeholder="Add a comment"
                                        value={newComment}
                                        onChange={(e) => setNewComment(e.target.value)}
                                        sx={{
                                            '& .MuiInputBase-root': {
                                                maxHeight: 'calc(4em + 32px)',
                                                overflowY: 'auto'
                                            }
                                        }}
                                    />
                                    <Button
                                        variant="contained"
                                        onClick={handleCommentSubmit}
                                        disabled={!newComment.trim()}
                                        sx={{ ml: 1, height: '56px' }}
                                    >
                                        Post
                                    </Button>
                                </Box>
                            </Box>
                            {/* </Stack> */}

                        </Paper>
                    </Grid>
                )}
                {selectedComment !== null && (
                    <CommentPopper
                        id={commentPopperId}
                        open={commentOpen}
                        anchorEl={commentAnchorEl}
                        comment={comments[selectedComment]}
                        onClose={() => {
                            setCommentAnchorEl(null);
                            setSelectedComment(null);
                        }}
                    />
                )}
                {/* Metadata and Activity Log */}
                <Grid item xs={12}>
                    <Paper elevation={3} sx={{ p: 2 }}>
                        <Typography variant="h6">Metadata</Typography>
                        <Divider sx={{ my: 1 }} />

                        {metadataAccordions.map((parentAccordion, parentIndex) => (
                            <Accordion
                                key={parentAccordion.category}
                                expanded={expandedAccordions[`parent-${parentIndex}`] || false}
                                onChange={handleAccordionChange(`parent-${parentIndex}`)}
                            >
                                <AccordionSummary
                                    expandIcon={<ExpandMoreIcon />}
                                    aria-controls={`parent-${parentIndex}-content`}
                                    id={`parent-${parentIndex}-header`}
                                >
                                    <Typography sx={{ fontWeight: 'bold' }}>
                                        {parentAccordion.category} ({parentAccordion.count})
                                    </Typography>
                                </AccordionSummary>
                                <AccordionDetails>
                                    {parentAccordion.subCategories.map((subAccordion, subIndex) => (
                                        <Accordion
                                            key={subAccordion.category}
                                            expanded={expandedAccordions[`sub-${parentIndex}-${subIndex}`] || false}
                                            onChange={handleAccordionChange(`sub-${parentIndex}-${subIndex}`)}
                                        >
                                            <AccordionSummary
                                                expandIcon={<ExpandMoreIcon />}
                                                aria-controls={`sub-${parentIndex}-${subIndex}-content`}
                                                id={`sub-${parentIndex}-${subIndex}-header`}
                                            >
                                                <Typography sx={{ fontWeight: 'bold' }}>
                                                    {subAccordion.category} ({subAccordion.count})
                                                </Typography>
                                            </AccordionSummary>
                                            <AccordionDetails>
                                                <MetadataContent
                                                    data={subAccordion.data}
                                                    showAll={expandedMetadata[`${parentIndex}-${subIndex}`]}
                                                />
                                                <Button
                                                    onClick={() => toggleMetadataExpansion(`${parentIndex}-${subIndex}`)}
                                                    sx={{ mt: 1 }}
                                                >
                                                    {expandedMetadata[`${parentIndex}-${subIndex}`] ? 'Show Less' : 'Show More'}
                                                </Button>
                                            </AccordionDetails>
                                        </Accordion>
                                    ))}
                                </AccordionDetails>
                            </Accordion>
                        ))}
                    </Paper>
                </Grid>
                <Grid item xs={12}>
                    <Paper elevation={3} sx={{ p: 2 }}>
                        <Typography variant="h6">Activity Log</Typography>
                        <Divider sx={{ my: 1 }} />
                        <List sx={{ width: '100%', bgcolor: 'background.paper' }}>
                            {[
                                { user: "John Doe", action: "Uploaded image", timestamp: "2023-06-15 09:30:22", isHuman: true },
                                { user: "AI Pipeline", action: "Performed image analysis", timestamp: "2023-06-15 09:31:05", icon: <AutoFixHighIcon /> },
                                { user: "Jane Smith", action: "Added tag 'Product Shot'", timestamp: "2023-06-15 10:15:43", isHuman: true },
                                { user: "AI Pipeline", action: "Generated image metadata", timestamp: "2023-06-15 10:16:30", icon: <DescriptionIcon /> },
                                { user: "Mike Johnson", action: "Edited image description", timestamp: "2023-06-15 11:22:17", isHuman: true },
                                { user: "Sarah Brown", action: "Initiated color correction pipeline", timestamp: "2023-06-15 13:45:09", isHuman: true },
                                { user: "AI Pipeline", action: "Completed color correction", timestamp: "2023-06-15 13:47:32", icon: <ColorLensIcon /> },
                                { user: "Tom Wilson", action: "Approved image for use", timestamp: "2023-06-15 14:30:00", isHuman: true },
                                { user: "Emily Davis", action: "Downloaded high-res version", timestamp: "2023-06-15 15:12:55", isHuman: true },
                                { user: "System", action: "Backup created", timestamp: "2023-06-15 23:00:00", icon: <BackupIcon /> },
                            ].map((activity, index) => (
                                <ListItem key={index}>
                                    <ListItemAvatar>
                                        {activity.isHuman ? (
                                            <Avatar src="https://mui.com/static/images/avatar/1.jpg" />
                                        ) : (
                                            <Avatar>
                                                {activity.icon}
                                            </Avatar>
                                        )}
                                    </ListItemAvatar>
                                    <ListItemText
                                        primary={activity.action}
                                        secondary={`${activity.user} - ${activity.timestamp}`}
                                    />
                                </ListItem>
                            ))}
                        </List>
                    </Paper>
                </Grid>


            </Grid>
        </Box >
    );
};
export default ImageDetailPage;