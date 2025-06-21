import React, { useState, useMemo, useCallback, useRef, useEffect } from 'react';
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
import { useAsset, useRelatedVersions, useTranscription, RelatedVersionsResponse, TranscriptionResponse } from '../api/hooks/useAssets';
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
import { AssetResponse } from '../api/types/asset.types';
import { formatFileSize } from '../utils/imageUtils';

// MUI Icons
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import CodeOutlinedIcon from '@mui/icons-material/CodeOutlined';
import LinkOutlinedIcon from '@mui/icons-material/LinkOutlined';
import SubtitlesOutlinedIcon from '@mui/icons-material/SubtitlesOutlined';
import MarkdownRenderer from '../components/common/MarkdownRenderer';



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

// Tab content components
const SummaryTab = ({ metadataFields, assetData }: { metadataFields: any, assetData: any }) => {
    const theme = useTheme();
    const fileInfoColor = '#4299E1';      // Blue
    const techDetailsColor = '#68D391';   // Green/teal
    const descKeywordsColor = '#F6AD55';  // Orange
    
    const s3Bucket = assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.Bucket;
    const objectName = assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.ObjectKey?.Name;
    const fullPath = assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.ObjectKey?.FullPath;
    const s3Uri = s3Bucket && fullPath ? `s3://${s3Bucket}/${fullPath}` : 'Unknown';

    // Extract metadata from API response
    const metadata = assetData?.data?.asset?.Metadata?.EmbeddedMetadata || {};
    const generalMetadata = metadata.general || {};
    const videoMetadata = Array.isArray(metadata.video) ? metadata.video[0] : {};
    

    const fileSize = assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.FileInfo?.Size || 0;
    const format = assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.Format || 'Unknown';
    const duration = generalMetadata.Duration ? `${parseFloat(generalMetadata.Duration).toFixed(2)} s` : 'Unknown';
    const width = videoMetadata.Width ?? 'Unknown';
    const height = videoMetadata.Height ?? 'Unknown';
    const frameRate = videoMetadata.FrameRate ? `${videoMetadata.FrameRate} FPS` : 'Unknown';
    const bitRate = (videoMetadata.OverallBitRate || videoMetadata.BitRate)
      ? `${Math.round((videoMetadata.OverallBitRate || videoMetadata.BitRate) / 1000)} kbps`
      : 'Unknown';
    const codec = videoMetadata.codec_name || metadata.general.Format || 'Unknown';
    
    
    const createdDate = assetData?.data?.asset?.DigitalSourceAsset?.CreateDate
        ? new Date(assetData.data.asset.DigitalSourceAsset.CreateDate).toLocaleDateString()
        : 'Unknown';

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
                    <Typography sx={{ width: '120px', color: 'text.secondary', fontSize: '0.875rem' }}>Type:</Typography>
                    <Typography sx={{ flex: 1, fontSize: '0.875rem' }}>{assetData?.data?.asset?.DigitalSourceAsset?.Type || 'Video'}</Typography>
                </Box>
                
                <Box sx={{ display: 'flex', mb: 1 }}>
                    <Typography sx={{ width: '120px', color: 'text.secondary', fontSize: '0.875rem' }}>Size:</Typography>
                    <Typography sx={{ flex: 1, fontSize: '0.875rem' }}>
                        {formatFileSize(fileSize)}
                    </Typography>
                </Box>
                
                <Box sx={{ display: 'flex', mb: 1 }}>
                    <Typography sx={{ width: '120px', color: 'text.secondary', fontSize: '0.875rem' }}>Format:</Typography>
                    <Typography sx={{ flex: 1, fontSize: '0.875rem' }}>{format}</Typography>
                </Box>

                <Box sx={{ display: 'flex', mb: 1 }}>
                    <Typography sx={{ width: '120px', color: 'text.secondary', fontSize: '0.875rem' }}>S3 Bucket:</Typography>
                    <Typography sx={{ flex: 1, fontSize: '0.875rem', wordBreak: 'break-all' }}>
                        {s3Bucket || 'Unknown'}
                    </Typography>
                </Box>

                <Box sx={{ display: 'flex', mb: 1 }}>
                    <Typography sx={{ width: '120px', color: 'text.secondary', fontSize: '0.875rem' }}>Object Name:</Typography>
                    <Typography sx={{ flex: 1, fontSize: '0.875rem', wordBreak: 'break-all' }}>
                        {objectName || 'Unknown'}
                    </Typography>
                </Box>

                <Box sx={{ display: 'flex', mb: 1 }}>
                    <Typography sx={{ width: '120px', color: 'text.secondary', fontSize: '0.875rem' }}>S3 URI:</Typography>
                    <Typography sx={{ flex: 1, fontSize: '0.875rem', wordBreak: 'break-all' }}>
                        {s3Uri}
                    </Typography>
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
                    <Typography sx={{ width: '120px', color: 'text.secondary', fontSize: '0.875rem' }}>Duration:</Typography>
                    <Typography sx={{ flex: 1, fontSize: '0.875rem' }}>{duration} seconds</Typography>
                </Box>
                
                <Box sx={{ display: 'flex', mb: 1 }}>
                    <Typography sx={{ width: '120px', color: 'text.secondary', fontSize: '0.875rem' }}>Resolution:</Typography>
                    <Typography sx={{ flex: 1, fontSize: '0.875rem' }}>{width}x{height}</Typography>
                </Box>
                
                <Box sx={{ display: 'flex', mb: 1 }}>
                    <Typography sx={{ width: '120px', color: 'text.secondary', fontSize: '0.875rem' }}>Frame Rate:</Typography>
                    <Typography sx={{ flex: 1, fontSize: '0.875rem' }}>{frameRate} FPS</Typography>
                </Box>
                
                <Box sx={{ display: 'flex', mb: 1 }}>
                    <Typography sx={{ width: '120px', color: 'text.secondary', fontSize: '0.875rem' }}>Bit Rate:</Typography>
                    <Typography sx={{ flex: 1, fontSize: '0.875rem' }}>{bitRate}</Typography>
                </Box>
                
                <Box sx={{ display: 'flex', mb: 1 }}>
                    <Typography sx={{ width: '120px', color: 'text.secondary', fontSize: '0.875rem' }}>Codec:</Typography>
                    <Typography sx={{ flex: 1, fontSize: '0.875rem' }}>{codec}</Typography>
                </Box>
                
                <Box sx={{ display: 'flex', mb: 1 }}>
                    <Typography sx={{ width: '120px', color: 'text.secondary', fontSize: '0.875rem' }}>Created Date:</Typography>
                    <Typography sx={{ flex: 1, fontSize: '0.875rem' }}>
                        {createdDate}
                    </Typography>
                </Box>
            </Box>
            
            {/* Description & Keywords Section */}
            {/* <Box sx={{ mb: 3 }}>
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
                    {metadataFields.descriptive.find((item: any) => item.label === 'Description')?.value || 'No description available'}
                </Typography>
                
                <Box sx={{ 
                    display: 'flex', 
                    flexWrap: 'wrap', 
                    gap: 0.75
                }}>
                    {(metadataFields.descriptive.find((item: any) => item.label === 'Keywords')?.value || 'video,footage')
                        .split(',')
                        .map((keyword: string, index: number) => (
                            <Chip
                                key={index}
                                label={keyword.trim()}
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
            </Box> */}
        </Box>
    );
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

const TranscriptionTab: React.FC<{
    assetId: string;
    transcriptionData: TranscriptionResponse | undefined;
    isLoading: boolean;
    assetData: any;
}> = ({ assetId, transcriptionData, isLoading, assetData }) => {
    const theme = useTheme();
    
    // Handle loading state
    if (isLoading) {
        return (
            <Box sx={{ p: 2, display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '300px' }}>
                <CircularProgress />
            </Box>
        );
    }
    
    // Handle missing or invalid data
    if (!transcriptionData || !transcriptionData.data || !transcriptionData.data.results) {
        return (
            <Box sx={{ p: 2, textAlign: 'center' }}>
                <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>
                    Video Transcription
                </Typography>
                <Paper elevation={0} sx={{
                    mb: 3,
                    p: 4,
                    backgroundColor: alpha(theme.palette.background.paper, 0.7),
                    borderRadius: 1,
                    border: `1px solid ${alpha(theme.palette.divider, 0.1)}`
                }}>
                    <Typography variant="body1" color="text.secondary">
                        No transcription data available for this video file.
                    </Typography>
                </Paper>
            </Box>
        );
    }
    
    // Check if transcripts array exists and has items
    const hasTranscripts = transcriptionData.data.results.transcripts &&
                          transcriptionData.data.results.transcripts.length > 0;
    
    // Check if items array exists
    const hasItems = transcriptionData.data.results.items &&
                    transcriptionData.data.results.items.length > 0;

    // Extract summary from asset data
    const summary = assetData?.data?.asset?.Summary100Result;

    return (
        <Box sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>
                Video Transcription
            </Typography>
            
            {/* Summary Section */}
            {summary && (
                <Paper elevation={0} sx={{
                    mb: 3,
                    p: 2,
                    backgroundColor: alpha(theme.palette.background.paper, 0.7),
                    borderRadius: 1,
                    border: `1px solid ${alpha(theme.palette.divider, 0.1)}`
                }}>
                    <Typography variant="body2" sx={{ mb: 2, fontStyle: 'italic', color: theme.palette.text.secondary }}>
                        Summary:
                    </Typography>
                    <MarkdownRenderer content={summary} />
                </Paper>
            )}
            
            <Paper elevation={0} sx={{
                mb: 3,
                p: 2,
                backgroundColor: alpha(theme.palette.background.paper, 0.7),
                borderRadius: 1,
                border: `1px solid ${alpha(theme.palette.divider, 0.1)}`
            }}>
                <Typography variant="body2" sx={{ mb: 2, fontStyle: 'italic', color: theme.palette.text.secondary }}>
                    Full Transcript:
                </Typography>
                <Typography variant="body1" paragraph>
                    {hasTranscripts
                        ? transcriptionData.data.results.transcripts[0].transcript
                        : "Full transcript not available"}
                </Typography>
            </Paper>
            
            {hasItems && (
                <>
                    <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 600 }}>
                        Time-Aligned Segments
                    </Typography>
                    
                    <Paper elevation={0} sx={{
                        backgroundColor: alpha(theme.palette.background.paper, 0.5),
                        borderRadius: 1
                    }}>
                        {transcriptionData.data.results.items.map((item, index) => (
                            <Box
                                key={index}
                                sx={{
                                    display: 'flex',
                                    p: 1.5,
                                    borderBottom: index < transcriptionData.data.results.items.length - 1 ?
                                        `1px solid ${alpha(theme.palette.divider, 0.1)}` : 'none',
                                    '&:hover': {
                                        backgroundColor: alpha(theme.palette.primary.main, 0.03)
                                    }
                                }}
                            >
                                <Box sx={{
                                    minWidth: '100px',
                                    pr: 2,
                                    borderRight: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                                    display: 'flex',
                                    flexDirection: 'column'
                                }}>
                                    <Typography variant="caption" sx={{ color: theme.palette.text.secondary }}>
                                        {`${item.start_time}s - ${item.end_time}s`}
                                    </Typography>
                                    {item.alternatives && item.alternatives.length > 0 && item.alternatives[0].confidence && (
                                        <Chip
                                            size="small"
                                            label={`${Math.round(parseFloat(item.alternatives[0].confidence) * 100)}%`}
                                            sx={{
                                                height: '18px',
                                                mt: 0.5,
                                                fontSize: '0.65rem',
                                                backgroundColor: (() => {
                                                    const conf = parseFloat(item.alternatives[0].confidence);
                                                    if (conf >= 0.95) return alpha(theme.palette.success.main, 0.1);
                                                    if (conf >= 0.85) return alpha(theme.palette.warning.main, 0.1);
                                                    return alpha(theme.palette.error.main, 0.1);
                                                })(),
                                                color: (() => {
                                                    const conf = parseFloat(item.alternatives[0].confidence);
                                                    if (conf >= 0.95) return theme.palette.success.main;
                                                    if (conf >= 0.85) return theme.palette.warning.main;
                                                    return theme.palette.error.main;
                                                })()
                                            }}
                                        />
                                    )}
                                </Box>
                                <Box sx={{ pl: 2, flex: 1 }}>
                                    {item.alternatives && item.alternatives.length > 0 ? (
                                        <>
                                            <Typography variant="body2">
                                                {item.alternatives[0].content}
                                            </Typography>
                                            {item.alternatives.length > 1 && (
                                                <Box sx={{ mt: 1 }}>
                                                    <Typography variant="caption" sx={{ color: theme.palette.text.secondary }}>
                                                        Alternatives:
                                                    </Typography>
                                                    {item.alternatives.slice(1).map((alt, altIndex) => {
                                                        const confidenceValue = alt.confidence ? Math.round(parseFloat(alt.confidence) * 100) : 'N/A';
                                                        return (
                                                            <Typography key={altIndex} variant="caption" sx={{
                                                                display: 'block',
                                                                color: theme.palette.text.secondary,
                                                                fontStyle: 'italic',
                                                                pl: 1
                                                            }}>
                                                                {alt.content} ({confidenceValue}%)
                                                            </Typography>
                                                        );
                                                    })}
                                                </Box>
                                            )}
                                        </>
                                    ) : (
                                        <Typography variant="body2" color="text.secondary">
                                            No content available
                                        </Typography>
                                    )}
                                </Box>
                            </Box>
                        ))}
                    </Paper>
                </>
            )}
            
            <Box sx={{ mt: 3, display: 'flex', justifyContent: 'center' }}>
                <Button
                    variant="outlined"
                    startIcon={<SubtitlesOutlinedIcon />}
                    sx={{ mr: 2 }}
                    disabled={!hasTranscripts}
                >
                    Export Transcript
                </Button>
                <Button
                    variant="outlined"
                    startIcon={<CodeOutlinedIcon />}
                >
                    Show Raw JSON
                </Button>
            </Box>
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

const VideoDetailContent: React.FC<VideoDetailContentProps> = ({
    asset,
    assetType,
    searchTerm
}) => {
    const videoViewerRef = useRef<VideoViewerRef>(null);
    console.log("Parent videoViewerRef:", videoViewerRef); // Debug log
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const location = useLocation();
    const { isExpanded, closeSidebar } = useRightSidebar();
    const { data: assetData, isLoading, error } = useAsset(id || '') as { data: AssetResponse | undefined; isLoading: boolean; error: any };
    const [activeTab, setActiveTab] = useState<string>('summary');
    const [relatedPage, setRelatedPage] = useState(1);
    const { data: relatedVersionsData, isLoading: isLoadingRelated } = useRelatedVersions(id || '', relatedPage);
    const { data: transcriptionData, isLoading: isLoadingTranscription } = useTranscription(id || '');
    const [showHeader, setShowHeader] = useState(true);

    const [expandedMetadata, setExpandedMetadata] = useState<{ [key: string]: boolean }>({});
    const [comments, setComments] = useState([
        { user: "John Doe", avatar: "https://mui.com/static/videos/avatar/1.jpg", content: "Great composition!", timestamp: "2023-06-15 09:30:22" },
        { user: "Jane Smith", avatar: "https://mui.com/static/videos/avatar/2.jpg", content: "The lighting is perfect", timestamp: "2023-06-15 10:15:43" },
        { user: "Mike Johnson", avatar: "https://mui.com/static/videos/avatar/3.jpg", content: "Can we adjust the contrast?", timestamp: "2023-06-15 11:22:17" },
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

    // Use the searchTerm prop or fallback to URL parameters
    const searchParams = new URLSearchParams(location.search);
    const urlSearchTerm = searchParams.get('q') || searchParams.get('searchTerm') || '';
    // Use the prop value if available, otherwise use the URL value
    const effectiveSearchTerm = searchTerm || urlSearchTerm;

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
            searchTerm: effectiveSearchTerm,
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
        const tabs = ['summary', 'technical', 'transcription', 'related'];
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
            navigate(`/search${effectiveSearchTerm ? `?q=${encodeURIComponent(effectiveSearchTerm)}` : ''}`);
        }
    }, [navigate, location.state, effectiveSearchTerm]);

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
                    searchTerm={effectiveSearchTerm}
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
        <Box 
            sx={{
                display: 'flex',
                flexDirection: 'column',
                maxWidth: isExpanded ? 'calc(100% - 300px)' : '100%',
                width: '100%',
                transition: theme => theme.transitions.create(['max-width'], {
                    easing: theme.transitions.easing.sharp,
                    duration: theme.transitions.duration.enteringScreen,
                }),
                bgcolor: 'transparent',
            }}
        >
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
                <Box sx={{ py: 0, mb: 0 }}>
                    <BreadcrumbNavigation
                        searchTerm={effectiveSearchTerm}
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

            <Box sx={{ px: 3, pt: 0, pb: 0, mt: 0, height: '75vh', minHeight: '600px', flexShrink: 0, display: 'flex', flexDirection: 'column' }}>
                <Paper
                    elevation={0}
                    sx={{
                        overflow: 'hidden',
                        borderRadius: 2,
                        background: 'transparent',
                        position: 'relative',
                        height: '100%',
                        width: '100%',
                        maxWidth: isExpanded ? 'calc(100% - 10px)' : '100%',
                        transition: theme => theme.transitions.create(['width', 'max-width'], {
                            easing: theme.transitions.easing.sharp,
                            duration: theme.transitions.duration.enteringScreen,
                        }),
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
                            overflow: 'visible',
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
                                value="transcription"
                                label="Transcription"
                                id="tab-transcription"
                                aria-controls="tabpanel-transcription"
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
                                backgroundColor: theme => alpha(theme.palette.background.paper, 0.5),
                                maxHeight: 'none',
                                overflow: 'visible'
                            }}
                            role="tabpanel"
                            id={`tabpanel-${activeTab}`}
                            aria-labelledby={`tab-${activeTab}`}
                            tabIndex={0} // Make the panel focusable
                        >
                            {activeTab === 'summary' && <SummaryTab metadataFields={metadataFields} assetData={assetData} />}
                            {activeTab === 'technical' && <TechnicalMetadataTab metadataAccordions={metadataAccordions} />}
                            {activeTab === 'transcription' && (
                                <TranscriptionTab
                                    assetId={id || ''}
                                    transcriptionData={transcriptionData}
                                    isLoading={isLoadingTranscription}
                                    assetData={assetData}
                                />
                            )}
                            {activeTab === 'related' && (
                                <RelatedItemsTab
                                    assetId={id || ''}
                                    relatedVersionsData={relatedVersionsData}
                                    isLoading={isLoadingRelated}
                                    onLoadMore={() => setRelatedPage(prev => prev + 1)}
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
                assetId={assetData?.data?.asset?.InventoryID}
                asset={asset}
                assetType={assetType}
                searchTerm={effectiveSearchTerm}
            />
        </Box>
    );
};

interface VideoDetailContentProps {
    asset: any;
    assetType: string;
    searchTerm?: string;
}

const VideoDetailPage: React.FC = () => {
    const location = useLocation();
    const { assetType, searchTerm, asset } = location.state;
    console.log('Asset type: ',assetType); // The DigitalSourceAsset.Type
    console.log('SearchTerm: ',searchTerm); // The currentQuery value
    console.log('Asset: ',asset); // The full asset object
    return (
        <RecentlyViewedProvider>
            <RightSidebarProvider>
                <VideoDetailContent
                    asset={asset}
                    assetType={assetType}
                    searchTerm={searchTerm}
                />
            </RightSidebarProvider>
        </RecentlyViewedProvider>
    );
};

export default VideoDetailPage;
