import React, { useState, useMemo, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  CircularProgress,
  Typography,
  List,
  ListItem,
  Paper,
  Button,
  Tabs,
  Tab,
  Grid,
  Card,
  CardContent,
  Chip,
  useTheme,
  alpha,
  TextField,
  InputAdornment,
  FormControl,
  Select,
  MenuItem,
  IconButton,
  CardHeader,
  ListItemText,
  LinearProgress
} from '@mui/material';
import { useAsset, useRelatedVersions } from '../api/hooks/useAssets';
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
import { Chip as MuiChip } from '@mui/material';

// MUI Icons
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import CodeOutlinedIcon from '@mui/icons-material/CodeOutlined';
import LinkOutlinedIcon from '@mui/icons-material/LinkOutlined';
import ZoomOutMapIcon from '@mui/icons-material/ZoomOutMap';
import SearchIcon from '@mui/icons-material/Search';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import EditIcon from '@mui/icons-material/Edit';
import CheckIcon from '@mui/icons-material/Check';
import CloseIcon from '@mui/icons-material/Close';

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

// Color coding for metadata categories
const getMetadataCategoryColor = (category: string, theme: any) => {
    const categoryColors: Record<string, string> = {
        'EXIF': theme.palette.primary.main,
        'GPS': theme.palette.success.main,
        'XMP': theme.palette.warning.main,
        'IPTC': theme.palette.info.main,
        'ICC': theme.palette.secondary.main,
        'general': theme.palette.grey[600],
        'technical': theme.palette.primary.light,
        'descriptive': theme.palette.secondary.light
    };
    
    // Try to find an exact match
    if (categoryColors[category]) return categoryColors[category];
    
    // Try to find a partial match
    const foundKey = Object.keys(categoryColors).find(key => 
        category.toLowerCase().includes(key.toLowerCase())
    );
    
    return foundKey ? categoryColors[foundKey] : categoryColors.general;
};

// Add this component for tag input
const TagInput: React.FC<{
    tags: string[];
    onChange: (newTags: string[]) => void;
}> = ({ tags, onChange }) => {
    const [inputValue, setInputValue] = useState('');
    
    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setInputValue(e.target.value);
    };
    
    const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if ((e.key === ' ' || e.key === 'Enter') && inputValue.trim()) {
            e.preventDefault();
            const newTag = inputValue.trim();
            
            // Only add if it's not a duplicate
            if (!tags.includes(newTag)) {
                onChange([...tags, newTag]);
            }
            
            setInputValue('');
        } else if (e.key === 'Backspace' && !inputValue && tags.length > 0) {
            // Remove the last tag when backspace is pressed in an empty input
            onChange(tags.slice(0, -1));
        }
    };
    
    const handleDeleteTag = (tagToDelete: string) => {
        onChange(tags.filter(tag => tag !== tagToDelete));
    };
    
    return (
        <Box 
            sx={{ 
                display: 'flex', 
                flexWrap: 'wrap', 
                gap: 0.5, 
                alignItems: 'center',
                p: 1,
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: 1,
                minHeight: 32
            }}
        >
            {tags.map(tag => (
                <MuiChip
                    key={tag}
                    label={tag}
                    size="small"
                    onDelete={() => handleDeleteTag(tag)}
                    sx={{ height: 24 }}
                />
            ))}
            <input
                value={inputValue}
                onChange={handleInputChange}
                onKeyDown={handleInputKeyDown}
                placeholder={tags.length > 0 ? '' : 'Type and press space to add tags'}
                style={{
                    flex: '1 0 50px',
                    minWidth: 60,
                    border: 'none',
                    outline: 'none',
                    background: 'transparent',
                    padding: '4px 0',
                    fontSize: '0.9rem'
                }}
            />
        </Box>
    );
};

const SummaryTab = ({ assetData }: { assetData: any }) => {
    const theme = useTheme();
    const asset = assetData?.data?.asset;
    const metadata = asset?.DigitalSourceAsset?.MainRepresentation?.Metadata || {};
    const filename = asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.ObjectKey?.Name || 'Unknown';
    const fileSize = asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.Size || 0;
    const fileType = asset?.DigitalSourceAsset?.MainRepresentation?.MediaFormat?.AssetType || 'Unknown';
    const fileFormat = asset?.DigitalSourceAsset?.MainRepresentation?.MediaFormat?.Format || 'Unknown';
    const dimensions = metadata?.Common?.VisualInfo?.Dimensions 
        ? `${metadata.Common.VisualInfo.Dimensions.Width}x${metadata.Common.VisualInfo.Dimensions.Height}`
        : 'Unknown';
    const createdDate = metadata?.Common?.CreationDate || 'Unknown';
    const description = metadata?.Common?.Description || 'High resolution landscape image';
    
    // Extract keywords/tags
    const keywords = metadata?.Common?.Keywords || ['nature', 'landscape'];
    
    // Colors matching the image exactly
    const fileInfoColor = '#4299E1';      // Blue
    const techDetailsColor = '#68D391';   // Green/teal
    const descKeywordsColor = '#F6AD55';  // Orange
    
    return (
        <Box>
            {/* File Information Section */}
            <Box sx={{ mb: 3 }}>
                <Typography 
                    sx={{ 
                        color: fileInfoColor,
                        fontSize: '0.875rem',
                        fontWeight: 600,
                        mb: 0.5
                    }}
                >
                    File Information
                </Typography>
                <Box sx={{ 
                    width: '100%', 
                    height: '1px', 
                    bgcolor: fileInfoColor,
                    mb: 2
                }} />
                
                <Box sx={{ display: 'flex', mb: 1 }}>
                    <Typography sx={{ width: '120px', color: 'text.secondary', fontSize: '0.875rem' }}>Title:</Typography>
                    <Typography sx={{ flex: 1, fontSize: '0.875rem' }}>{filename}</Typography>
                </Box>
                
                <Box sx={{ display: 'flex', mb: 1 }}>
                    <Typography sx={{ width: '120px', color: 'text.secondary', fontSize: '0.875rem' }}>Type:</Typography>
                    <Typography sx={{ flex: 1, fontSize: '0.875rem' }}>{fileType}</Typography>
                </Box>
                
                <Box sx={{ display: 'flex', mb: 1 }}>
                    <Typography sx={{ width: '120px', color: 'text.secondary', fontSize: '0.875rem' }}>Size:</Typography>
                    <Typography sx={{ flex: 1, fontSize: '0.875rem' }}>{formatFileSize(fileSize)}</Typography>
                </Box>
                
                <Box sx={{ display: 'flex', mb: 1 }}>
                    <Typography sx={{ width: '120px', color: 'text.secondary', fontSize: '0.875rem' }}>Format:</Typography>
                    <Typography sx={{ flex: 1, fontSize: '0.875rem' }}>{fileFormat}</Typography>
                </Box>
            </Box>
            
            {/* Technical Details Section */}
            <Box sx={{ mb: 3 }}>
                <Typography 
                    sx={{ 
                        color: techDetailsColor,
                        fontSize: '0.875rem',
                        fontWeight: 600,
                        mb: 0.5
                    }}
                >
                    Technical Details
                </Typography>
                <Box sx={{ 
                    width: '100%', 
                    height: '1px', 
                    bgcolor: techDetailsColor,
                    mb: 2
                }} />
                
                <Box sx={{ display: 'flex', mb: 1 }}>
                    <Typography sx={{ width: '120px', color: 'text.secondary', fontSize: '0.875rem' }}>Dimensions:</Typography>
                    <Typography sx={{ flex: 1, fontSize: '0.875rem' }}>{dimensions}</Typography>
                </Box>
                
                <Box sx={{ display: 'flex', mb: 1 }}>
                    <Typography sx={{ width: '120px', color: 'text.secondary', fontSize: '0.875rem' }}>Created Date:</Typography>
                    <Typography sx={{ flex: 1, fontSize: '0.875rem' }}>
                        {typeof createdDate === 'string' ? createdDate : formatLocalDateTime(createdDate)}
                    </Typography>
                </Box>
            </Box>
            
            {/* Description & Keywords Section */}
            <Box sx={{ mb: 3 }}>
                <Typography 
                    sx={{ 
                        color: descKeywordsColor,
                        fontSize: '0.875rem',
                        fontWeight: 600,
                        mb: 0.5
                    }}
                >
                    Description & Keywords
                </Typography>
                <Box sx={{ 
                    width: '100%', 
                    height: '1px', 
                    bgcolor: descKeywordsColor,
                    mb: 2
                }} />
                
                <Typography sx={{ fontSize: '0.875rem', mb: 2 }}>
                    {description}
                </Typography>
                
                <Box sx={{ 
                    display: 'flex', 
                    flexWrap: 'wrap', 
                    gap: 0.75
                }}>
                    {keywords.map((keyword, index) => (
                        <Chip
                            key={index}
                            label={keyword}
                            size="small"
                            sx={{
                                bgcolor: '#1E2732',
                                color: '#fff',
                                borderRadius: '16px',
                                fontSize: '0.75rem'
                            }}
                        />
                    ))}
                </Box>
            </Box>
        </Box>
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
            <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
                <TextField
                    placeholder="Filter metadata..." 
                    size="small"
                    InputProps={{
                        startAdornment: (
                            <InputAdornment position="start">
                                <SearchIcon fontSize="small" />
                            </InputAdornment>
                        ),
                    }}
                    onChange={(e) => {
                        // Implement filtering logic here
                    }}
                    sx={{ flex: 1 }}
                />
                <FormControl size="small" sx={{ minWidth: 120 }}>
                    <Select
                        value="all"
                        onChange={(e) => {/* Category filter logic */}}
                        displayEmpty
                    >
                        <MenuItem value="all">All Categories</MenuItem>
                        {Object.keys(categoryMapping).map(category => (
                            <MenuItem key={category} value={category}>{categoryMapping[category]}</MenuItem>
                        ))}
                    </Select>
                </FormControl>
            </Box>
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
                            <Box sx={{ 
                                display: 'flex', 
                                alignItems: 'center',
                                py: 0.5,
                                pl: 1,
                                borderLeft: `3px solid ${getMetadataCategoryColor(parentAccordion.category, theme)}`,
                                borderRadius: '4px 0 0 4px',
                            }}>
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
                                        backgroundColor: alpha(getMetadataCategoryColor(parentAccordion.category, theme), 0.1),
                                        color: getMetadataCategoryColor(parentAccordion.category, theme)
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

const DescriptorMetadataTab: React.FC<{ assetData: any }> = ({ assetData }) => {
    const theme = useTheme();
    
    // This would typically contain descriptive metadata like who/what is in the image
    // For now, we'll use placeholder data
    const descriptiveData = [
        {
            label: 'Description',
            value: 'High-resolution image from the collection',
            icon: <DescriptionOutlinedIcon fontSize="small" sx={{ color: theme.palette.secondary.main }} />
        },
        {
            label: 'Keywords',
            value: 'nature, landscape, photography',
            icon: <InfoOutlinedIcon fontSize="small" sx={{ color: theme.palette.secondary.main }} />
        },
        {
            label: 'Location',
            value: 'Unknown',
            icon: <InfoOutlinedIcon fontSize="small" sx={{ color: theme.palette.secondary.main }} />
        },
        {
            label: 'People',
            value: 'None identified',
            icon: <InfoOutlinedIcon fontSize="small" sx={{ color: theme.palette.secondary.main }} />
        },
        {
            label: 'Objects',
            value: 'Various natural elements',
            icon: <InfoOutlinedIcon fontSize="small" sx={{ color: theme.palette.secondary.main }} />
        }
    ];

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

const RelatedItemsTab: React.FC<{ assetId: string }> = ({ assetId }) => {
    const theme = useTheme();
    const [page, setPage] = useState(1);
    const { data: relatedVersionsData, isLoading } = useRelatedVersions(assetId, page);

    // Get icon based on item type
    const getItemIcon = (type: string) => {
        switch (type) {
            case 'image':
                return <DescriptionOutlinedIcon fontSize="small" sx={{ color: theme.palette.primary.main }} />;
            case 'video':
                return <CodeOutlinedIcon fontSize="small" sx={{ color: theme.palette.primary.main }} />;
            case 'audio':
                return <InfoOutlinedIcon fontSize="small" sx={{ color: theme.palette.primary.main }} />;
            default:
                return <LinkOutlinedIcon fontSize="small" sx={{ color: theme.palette.primary.main }} />;
        }
    };
    
    const relatedItems = useMemo(() => {
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

    if (isLoading) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
                <CircularProgress />
            </Box>
        );
    }

    return (
        <Box sx={{ p: 2, backgroundColor: alpha(theme.palette.background.paper, 0.5), borderRadius: 1 }}>
            <Grid container spacing={3}>
                {relatedItems.map((item) => (
                    <Grid item xs={12} sm={6} md={4} key={item.id}>
                        <Card
                            variant="outlined"
                            sx={{
                                height: '100%',
                                transition: 'all 0.2s ease-in-out',
                                '&:hover': {
                                    boxShadow: `0 4px 8px ${alpha(theme.palette.common.black, 0.1)}`,
                                    transform: 'translateY(-2px)'
                                },
                                cursor: 'pointer'
                            }}
                        >
                            <CardContent>
                                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                                    {getItemIcon(item.type)}
                                    <Typography
                                        variant="subtitle1"
                                        sx={{
                                            ml: 1,
                                            fontWeight: 600,
                                            color: theme.palette.text.primary
                                        }}
                                    >
                                        {item.title}
                                    </Typography>
                                </Box>
                                <Box sx={{ display: 'flex', gap: 1, mb: 1 }}>
                                    <Chip
                                        size="small"
                                        label={item.type.toUpperCase()}
                                        sx={{
                                            backgroundColor: alpha(theme.palette.primary.main, 0.1),
                                            color: theme.palette.primary.main,
                                            fontWeight: 500,
                                            fontSize: '0.75rem'
                                        }}
                                    />
                                    <Chip
                                        size="small"
                                        label={`Similarity: ${(item.score * 100).toFixed(1)}%`}
                                        sx={{
                                            backgroundColor: alpha(theme.palette.secondary.main, 0.1),
                                            color: theme.palette.secondary.main,
                                            fontWeight: 500,
                                            fontSize: '0.75rem'
                                        }}
                                    />
                                </Box>
                                <Typography variant="body2" color="text.secondary">
                                    {formatFileSize(item.fileSize)} • {item.format}
                                </Typography>
                                <Typography variant="body2" color="text.secondary">
                                    Created: {formatLocalDateTime(item.createDate)}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                ))}
            </Grid>
            
            {relatedVersionsData?.data?.totalResults > page * 50 && (
                <Box sx={{ display: 'flex', justifyContent: 'center', mt: 3 }}>
                    <Button
                        variant="outlined"
                        onClick={() => setPage(prev => prev + 1)}
                        startIcon={<ExpandMoreIcon />}
                    >
                        Load More
                    </Button>
                </Box>
            )}
        </Box>
    );
};

const MetadataContent: React.FC<MetadataContentProps> = ({ data, depth = 0, showAll, category }) => {
    const theme = useTheme();
    
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
            <Box sx={{ 
                display: 'grid', 
                gridTemplateColumns: {
                    xs: '1fr',
                    sm: 'repeat(auto-fill, minmax(180px, 1fr))',
                    md: 'repeat(auto-fill, minmax(200px, 1fr))'
                }, 
                gap: 2 
            }}>
                {displayEntries.map(([key, value]) => (
                    <Box key={key} sx={{
                        backgroundColor: alpha(theme.palette.background.paper, 0.7),
                        p: 1.5,
                        borderRadius: 1,
                        border: `1px solid ${alpha(theme.palette.divider, 0.1)}`
                    }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                            <Typography variant="body2" sx={{ fontWeight: 'bold', color: theme.palette.text.primary }}>
                                {formatCamelCase(key)}:
                            </Typography>
                            <IconButton 
                                size="small" 
                                onClick={() => navigator.clipboard.writeText(
                                    typeof value === 'object' ? JSON.stringify(value) : String(value)
                                )}
                                sx={{ opacity: 0.6, '&:hover': { opacity: 1 }, ml: 0.5, p: 0.3 }}
                            >
                                <ContentCopyIcon fontSize="small" sx={{ fontSize: '0.9rem' }} />
                            </IconButton>
                        </Box>
                        <Box sx={{ pl: 0 }}>
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
        return (
            <Typography 
                variant="body2" 
                sx={{ 
                    color: data === null || data === undefined 
                        ? theme.palette.text.disabled 
                        : theme.palette.text.primary,
                    fontStyle: data === null || data === undefined ? 'italic' : 'normal'
                }}
            >
                <TruncatedTextWithTooltip text={String(data)} />
            </Typography>
        );
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

    const handleAddComment = useCallback((content: string) => {
        const newCommentObj = {
            user: "Current User",
            avatar: "https://mui.com/static/images/avatar/4.jpg",
            content: content,
            timestamp: new Date().toISOString()
        };
        setComments(prev => [...prev, newCommentObj]);
        setNewComment('');
    }, []);

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
            bgcolor: 'transparent',
        }}>
            <Box sx={{
                position: 'sticky',
                top: 0,
                zIndex: 1200,
                background: 'transparent'
            }}>
                <Box sx={{ px: 0, py: 0, mb: 0 }}>
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
                gap: 1,
                px: 0,
                pb: 0,
                mt: 0
            }}>
                <Box sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 1
                }}>
                    <Box sx={{
                        position: 'relative',
                        bgcolor: 'transparent',
                        pt: 0,
                        pb: 0,
                        mt: 0,
                        mb: 0
                    }}>
                        <Box
                            sx={{
                                overflow: 'hidden',
                                borderRadius: 2,
                                position: 'relative'
                            }}
                        >
                            <ImageViewer imageSrc={proxyUrl} maxHeight={600} />
                            {/* <Box
                                sx={{
                                    position: 'absolute',
                                    top: 8,
                                    right: 8,
                                    bgcolor: 'rgba(255,255,255,0.8)',
                                    borderRadius: '50%',
                                    p: 0.5,
                                    cursor: 'pointer',
                                    '&:hover': {
                                        bgcolor: 'rgba(255,255,255,0.9)',
                                    }
                                }}
                            >
                                <ZoomOutMapIcon fontSize="small" color="primary" />
                            </Box> */}
                        </Box>
                    </Box>

                    <Box>
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
                                textColor="secondary"
                                indicatorColor="secondary"
                                aria-label="metadata tabs"
                                variant="scrollable"
                                scrollButtons="auto"
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
                                    label={
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            <InfoOutlinedIcon fontSize="small" />
                                            <span>Summary</span>
                                        </Box>
                                    }
                                    id="tab-summary"
                                    aria-controls="tabpanel-summary"
                                />
                                <Tab
                                    value="technical"
                                    label={
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            <CodeOutlinedIcon fontSize="small" />
                                            <span>Technical</span>
                                            {metadataAccordions.length > 0 && (
                                                <Chip 
                                                    size="small" 
                                                    label={metadataAccordions.length} 
                                                    sx={{ height: 20, ml: 0.5 }} 
                                                />
                                            )}
                                        </Box>
                                    }
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
                                    mt: { xs: 2, sm: 3 },
                                    mx: { xs: 1, sm: 2, md: 3 },
                                    mb: { xs: 2, sm: 3 },
                                    pt: { xs: 1, sm: 2 },
                                    outline: 'none',
                                    borderRadius: 1,
                                    backgroundColor: 'transparent'
                                }}
                                role="tabpanel"
                                id={`tabpanel-${activeTab}`}
                                aria-labelledby={`tab-${activeTab}`}
                                tabIndex={0}
                            >
                                {activeTab === 'summary' && <SummaryTab assetData={assetData} />}
                                {activeTab === 'technical' && <TechnicalMetadataTab metadataAccordions={metadataAccordions} />}
                                {activeTab === 'descriptor' && <DescriptorMetadataTab assetData={assetData} />}
                                {activeTab === 'related' && <RelatedItemsTab assetId={assetData.data.asset.DigitalSourceAsset.ID} />}
                            </Box>
                        </Paper>
                    </Box>
                </Box>

                <AssetSidebar
                    versions={versions}
                    comments={comments}
                    onAddComment={handleAddComment}
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