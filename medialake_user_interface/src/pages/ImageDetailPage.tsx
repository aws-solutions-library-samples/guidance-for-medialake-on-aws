import React, { useState, useMemo, useCallback, useEffect } from 'react';
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
import { useAsset, useRelatedVersions, RelatedVersionsResponse } from '../api/hooks/useAssets';
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
import { RelatedItemsView } from '../components/shared/RelatedItemsView';
import { RelatedVersionsResponse as NewRelatedVersionsResponse } from '../api/types/asset.types';

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
    const fileInfoColor = '#4299E1';      // Blue
    const techDetailsColor = '#68D391';   // Green/teal
    
    // Extract metadata from API response
    const metadata = asset?.Metadata?.EmbeddedMetadata || {};
    const generalMetadata = metadata?.General || {};
    const imageMetadata = metadata?.Image?.[0] || {};
    
    // Create a helper function to render a field only if it exists in the API response
    const renderField = (label: string, value: any, formatter?: (val: any) => string) => {
        if (value === undefined || value === null) return null;
        
        return (
            <Box sx={{ display: 'flex', mb: 1 }}>
                <Typography sx={{ width: '120px', color: 'text.secondary', fontSize: '0.875rem' }}>{label}:</Typography>
                <Typography sx={{ flex: 1, fontSize: '0.875rem', wordBreak: 'break-all' }}>
                    {formatter ? formatter(value) : value}
                </Typography>
            </Box>
        );
    };
    
    // File Information fields
    const fileSize = asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.FileInfo?.Size;
    const fileType = asset?.DigitalSourceAsset?.Type;
    const fileFormat = asset?.DigitalSourceAsset?.MainRepresentation?.Format;
    const s3Bucket = asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.Bucket;
    const objectName = asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.ObjectKey?.Name;
    const objectFullPath = asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.ObjectKey?.FullPath;
    const s3Uri = s3Bucket && objectFullPath ? `s3://${s3Bucket}/${objectFullPath}` : undefined;
    
    // Technical details
    const width = imageMetadata?.Width || generalMetadata?.ImageWidth;
    const height = imageMetadata?.Height || generalMetadata?.ImageHeight;
    const dimensions = width && height ? `${width}x${height}` : undefined;
    const colorDepth = imageMetadata?.BitDepth || imageMetadata?.Bitdepth;
    const colorSpace = imageMetadata?.ColorSpace || imageMetadata?.Colorspace;
    const compression = imageMetadata?.Compression || imageMetadata?.CompressionAlgorithm;
    const createdDate = asset?.DigitalSourceAsset?.CreateDate
        ? new Date(asset.DigitalSourceAsset.CreateDate).toLocaleDateString()
        : undefined;
    
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
                
                {renderField('Type', fileType)}
                {renderField('Size', fileSize, formatFileSize)}
                {renderField('Format', fileFormat)}
                {renderField('S3 Bucket', s3Bucket)}
                {renderField('Object Name', objectName)}
                {renderField('S3 URI', s3Uri)}
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
                
                {renderField('Dimensions', dimensions)}
                {renderField('Color Depth', colorDepth, (val) => `${val} bit`)}
                {renderField('Color Space', colorSpace)}
                {renderField('Compression', compression)}
                {renderField('Created Date', createdDate)}
            </Box>
        </Box>
    );
};

// Add new component for grid layout metadata display
const GridMetadataContent: React.FC<MetadataContentProps> = ({ data, depth = 0, showAll, category }) => {
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

    // Function to flatten nested objects like Tags/Encoder
    const flattenNestedMetadata = (entries: [string, any][]): [string, any][] => {
        const result: [string, any][] = [];
        
        entries.forEach(([key, value]) => {
            if (typeof value === 'object' && value !== null && !Array.isArray(value) && Object.keys(value).length > 0) {
                // Mark this as a parent with _PARENT_ prefix (for internal use)
                result.push([`_PARENT_${key}`, '']);
                
                // Then add the child properties with a visible indent prefix
                Object.entries(value).forEach(([subKey, subValue]) => {
                    result.push([`      ↳ ${subKey}`, subValue]);
                });
            } else {
                result.push([key, value]);
            }
        });
        
        return result;
    };

    // Function to identify parent-child relationships in entries
    const isParentEntry = (key: string): boolean => {
        return key.startsWith('_PARENT_');
    };

    const isChildEntry = (key: string): boolean => {
        return key.includes('↳');
    };

    // Function to clean display keys (remove internal markings)
    const cleanDisplayKey = (key: string): string => {
        if (key.startsWith('_PARENT_')) {
            return key.substring(8); // Remove the _PARENT_ prefix
        }
        return key;
    };

    if (Array.isArray(data)) {
        const displayData = showAll ? data : data.slice(0, 5);
        return (
            <List dense disablePadding>
                {displayData.map((item, index) => (
                    <ListItem key={index} sx={{ pl: depth * 2 }}>
                        <GridMetadataContent data={item} depth={depth + 1} showAll={showAll} category={category} />
                    </ListItem>
                ))}
            </List>
        );
    } else if (typeof data === 'object' && data !== null) {
        let entries = Object.entries(data);
        const sortedEntries = sortEntries(entries);
        // Flatten nested metadata
        const flattenedEntries = flattenNestedMetadata(sortedEntries);
        const displayEntries = showAll ? flattenedEntries : flattenedEntries.slice(0, 5);
        
        // Create rows efficiently while preserving parent-child relationships
        const rows: [string, any][][] = [];
        
        let currentIndex = 0;
        while (currentIndex < displayEntries.length) {
            const row: [string, any][] = [];
            
            // Process the left column
            if (currentIndex < displayEntries.length) {
                const leftEntry = displayEntries[currentIndex];
                const [leftKey] = leftEntry;
                
                // Parent entries must always be on the left side
                if (isParentEntry(leftKey)) {
                    row.push([cleanDisplayKey(leftKey), leftEntry[1]]);
                    currentIndex++;
                    
                    // In this case, we don't add a right column entry
                    // because we want to ensure the parent is alone on its row
                } else {
                    row.push(leftEntry);
                    currentIndex++;
                    
                    // Process the right column if available and not a parent
                    if (currentIndex < displayEntries.length) {
                        const rightEntry = displayEntries[currentIndex];
                        const [rightKey] = rightEntry;
                        
                        if (!isParentEntry(rightKey)) {
                            row.push(rightEntry);
                            currentIndex++;
                        }
                    }
                }
            }
            
            if (row.length > 0) {
                rows.push(row);
            }
        }

        return (
            <Box sx={{
                width: '100%',
                mb: 2,
                backgroundColor: alpha(theme.palette.background.paper, 0.3),
                borderRadius: 1,
                p: 2
            }}>
                {rows.map((row, rowIndex) => (
                    <Box 
                        key={rowIndex} 
                        sx={{
                            display: 'grid',
                            gridTemplateColumns: 'minmax(180px, 25%) minmax(180px, 25%) minmax(180px, 25%) minmax(180px, 25%)',
                            py: 1,
                            borderBottom: rowIndex < rows.length - 1 ? 
                                `1px solid ${alpha(theme.palette.divider, 0.1)}` : 'none',
                        }}
                    >
                        {row.map(([key, value], colIndex) => (
                            <React.Fragment key={`${rowIndex}-${colIndex}`}>
                                <Typography 
                                    variant="body2" 
                                    sx={{ 
                                        fontWeight: 'bold',
                                        color: key.trim().startsWith('↳') ? 
                                            theme.palette.primary.main : 
                                            theme.palette.text.secondary,
                                        textAlign: 'left',
                                        pr: 1
                                    }}
                                >
                                    {formatCamelCase(key)}:
                                </Typography>
                                <Box sx={{ mb: colIndex < row.length - 1 ? 0 : 1 }}>
                                    {typeof value === 'object' && value !== null ? (
                                        <GridMetadataContent
                                            data={value}
                                            depth={depth + 1}
                                            showAll={showAll}
                                            category={category}
                                        />
                                    ) : (
                                        <Typography 
                                            variant="body2" 
                                            sx={{ 
                                                wordBreak: 'break-word',
                                                whiteSpace: 'nowrap',
                                                overflow: 'hidden',
                                                textOverflow: 'ellipsis'
                                            }}
                                        >
                                            {String(value)}
                                        </Typography>
                                    )}
                                </Box>
                            </React.Fragment>
                        ))}
                    </Box>
                ))}
            </Box>
        );
    } else {
        return <Typography variant="body2">{String(data)}</Typography>;
    }
};

const TechnicalMetadataTab: React.FC<{ metadataAccordions: any[] }> = ({ metadataAccordions }) => {
    const theme = useTheme();
    
    // Create array of all item IDs to pre-expand them
    const [expandedItems] = useState<string[]>(() => {
        // Initialize with all items expanded
        const allItems: string[] = [];
        
        metadataAccordions.forEach((parent, parentIndex) => {
            // Add parent item
            allItems.push(`parent-${parentIndex}`);
            
            // Add all child items
            parent.subCategories.forEach((_, subIndex) => {
                allItems.push(`${parentIndex}-${subIndex}`);
            });
        });
        
        return allItems;
    });
    
    // Function to determine which content component to use based on category
    const getContentComponent = (subCategory: any) => {
        // Use GridMetadataContent for all categories to ensure consistent formatting
        return (
            <GridMetadataContent
                data={subCategory.data}
                showAll={true}
                category={subCategory.category}
            />
        );
    };
    
    return (
        <Box sx={{
            borderRadius: 1,
            width: '100%'
        }}>
            {/* Keep the filter bar */}
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
                defaultExpandedItems={expandedItems}
                sx={{
                    flexGrow: 1,
                    width: '100%',
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
                                    {parentAccordion.category === "EmbeddedMetadata" 
                                        ? "Embedded Metadata" 
                                        : parentAccordion.category}
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
                                    {getContentComponent(subCategory)}
                                </Box>
                            </TreeItem>
                        ))}
                    </TreeItem>
                ))}
            </SimpleTreeView>
        </Box>
    );
};

const RelatedItemsTab: React.FC<{ 
    assetId: string;
    relatedVersionsData: RelatedVersionsResponse | undefined;
    isLoading: boolean;
    onLoadMore: () => void;
}> = ({ assetId, relatedVersionsData, isLoading, onLoadMore }) => {
    console.log('RelatedItemsTab - relatedVersionsData:', relatedVersionsData);
    
    const items = useMemo(() => {
        if (!relatedVersionsData?.data?.results) {
            console.log('No results found in relatedVersionsData');
            return [];
        }

        const mappedItems = relatedVersionsData.data.results.map((result) => ({
            id: result.InventoryID,
            title: result.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name,
            type: result.DigitalSourceAsset.Type,
            thumbnail: result.thumbnailUrl,
            proxyUrl: result.proxyUrl,
            score: result.score,
            format: result.DigitalSourceAsset.MainRepresentation.Format,
            fileSize: result.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size,
            createDate: result.DigitalSourceAsset.CreateDate
        }));
        console.log('Mapped items:', mappedItems);
        return mappedItems;
    }, [relatedVersionsData]);

    const hasMore = useMemo(() => {
        if (!relatedVersionsData?.data?.searchMetadata) {
            console.log('No searchMetadata found for hasMore calculation');
            return false;
        }

        const { totalResults, page, pageSize } = relatedVersionsData.data.searchMetadata;
        const hasMoreItems = totalResults > page * pageSize;
        console.log('Has more items:', hasMoreItems);
        return hasMoreItems;
    }, [relatedVersionsData]);

    console.log('Rendering RelatedItemsView with items:', items);
    return (
        <RelatedItemsView
            items={items}
            isLoading={isLoading}
            onLoadMore={onLoadMore}
            hasMore={hasMore}
        />
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
    const navigate = useNavigate();
    const location = useLocation();
    const theme = useTheme();
    const [activeTab, setActiveTab] = useState('summary');
    const [relatedPage, setRelatedPage] = useState(1);
    const { data: assetData, isLoading: isLoadingAsset } = useAsset(id || '');
    const { data: relatedVersionsData, isLoading: isLoadingRelated } = useRelatedVersions(id || '', relatedPage);
    const { isExpanded, closeSidebar } = useRightSidebar();
    const [expandedMetadata, setExpandedMetadata] = useState<{ [key: string]: boolean }>({});
    const [commentAnchorEl, setCommentAnchorEl] = useState<null | HTMLElement>(null);
    const [selectedComment, setSelectedComment] = useState<number | null>(null);
    const [newComment, setNewComment] = useState('');
    const [showHeader, setShowHeader] = useState(true);
    const [comments, setComments] = useState([
        { user: "John Doe", avatar: "https://mui.com/static/images/avatar/1.jpg", content: "Great composition!", timestamp: "2023-06-15 09:30:22" },
        { user: "Jane Smith", avatar: "https://mui.com/static/images/avatar/2.jpg", content: "The lighting is perfect!", timestamp: "2023-06-15 10:15:45" },
        { user: "Mike Johnson", avatar: "https://mui.com/static/images/avatar/3.jpg", content: "Love the color palette!", timestamp: "2023-06-15 11:00:12" }
    ]);

    // Scroll to top when component mounts
    useEffect(() => {
        // Find the scrollable container in the AppLayout
        const container = document.querySelector('[class*="AppLayout"] [style*="overflow: auto"]');
        if (container) {
            container.scrollTo(0, 0);
        } else {
            // Fallback to window scrolling
            window.scrollTo(0, 0);
        }
    }, [id]); // Include id in dependencies to ensure scroll reset when navigating between detail pages

    // Track scroll position to hide/show header
    useEffect(() => {
        let lastScrollTop = 0;
        
        const handleScroll = () => {
            // Get scrollTop from the parent scrollable container instead
            const currentScrollTop = document.querySelector('[class*="AppLayout"] [style*="overflow: auto"]')?.scrollTop || 0;
            
            if (currentScrollTop <= 10) {
                setShowHeader(true);
            } else if (currentScrollTop > lastScrollTop) {
                setShowHeader(false);
            } else if (currentScrollTop < lastScrollTop) {
                setShowHeader(true);
            }
            
            lastScrollTop = currentScrollTop;
        };
        
        // Listen to scroll on the parent container
        const container = document.querySelector('[class*="AppLayout"] [style*="overflow: auto"]');
        if (container) {
            container.addEventListener('scroll', handleScroll, { passive: true });
        }
        
        return () => {
            if (container) {
                container.removeEventListener('scroll', handleScroll);
            }
        };
    }, []);

    const recentlyViewedItem = useMemo(() => {
        if (!id || !assetData?.data?.asset) return null;
        const asset = assetData.data.asset;
        return {
            id,
            title: asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name,
            type: asset.DigitalSourceAsset.Type.toLowerCase() as 'video' | 'image' | 'audio',
            path: location.pathname,
            searchTerm: '',
            metadata: {
                fileSize: formatFileSize(asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size)
            }
        };
    }, [id, assetData, location.pathname]);

    useTrackRecentlyViewed(recentlyViewedItem);

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

    console.log('ImageDetailContent - activeTab:', activeTab);
    console.log('ImageDetailContent - relatedVersionsData:', relatedVersionsData);
    console.log('ImageDetailContent - isLoadingRelated:', isLoadingRelated);

    const renderTabContent = () => {
        console.log('renderTabContent - activeTab:', activeTab);
        switch (activeTab) {
            case 'summary':
                return <SummaryTab assetData={assetData} />;
            case 'technical':
                return <TechnicalMetadataTab metadataAccordions={metadataAccordions} />;
            case 'related':
                console.log('Rendering RelatedItemsTab');
                return (
                    <RelatedItemsTab 
                        assetId={assetData.data.asset.DigitalSourceAsset.ID}
                        relatedVersionsData={relatedVersionsData}
                        isLoading={isLoadingRelated}
                        onLoadMore={() => setRelatedPage(prev => prev + 1)}
                    />
                );
            default:
                return null;
        }
    };

    if (isLoadingAsset) {
        return (
            <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
                <CircularProgress />
            </Box>
        );
    }

    if (!assetData) {
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
            maxWidth: isExpanded ? 'calc(100% - 300px)' : '100%',
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
                background: theme => alpha(theme.palette.background.default, 0.8),
                backdropFilter: 'blur(8px)',
                transform: showHeader ? 'translateY(0)' : 'translateY(-100%)',
                transition: 'transform 0.3s ease-in-out',
                visibility: showHeader ? 'visible' : 'hidden',
                opacity: showHeader ? 1 : 0,
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

            {/* Image viewer section */}
            <Box sx={{ px: 3, pt: 0, pb: 3, minHeight: '60vh' }}>
                <Box
                    sx={{
                        overflow: 'hidden',
                        borderRadius: 2,
                        position: 'relative'
                    }}
                >
                    <ImageViewer imageSrc={proxyUrl} maxHeight={600} />
                </Box>
            </Box>

            {/* Metadata section */}
            <Box sx={{ px: 3, pb: 3 }}>
                <Paper
                    elevation={0}
                    sx={{
                        p: 0,
                        borderRadius: 2,
                        overflow: 'visible',
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
                            backgroundColor: 'transparent',
                            overflow: 'visible',
                            maxHeight: 'none'
                        }}
                        role="tabpanel"
                        id={`tabpanel-${activeTab}`}
                        aria-labelledby={`tab-${activeTab}`}
                        tabIndex={0}
                    >
                        {renderTabContent()}
                    </Box>
                </Paper>
            </Box>

            <AssetSidebar
                versions={versions}
                comments={comments}
                onAddComment={handleAddComment}
                assetId={assetData?.data?.asset?.InventoryID}
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