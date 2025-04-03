import React, { useState, useMemo, useCallback, useEffect, useRef } from 'react';
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
import { useAsset, useRelatedVersions } from '../api/hooks/useAssets';
import { RightSidebarProvider, useRightSidebar } from '../components/common/RightSidebar';
import { RecentlyViewedProvider, useTrackRecentlyViewed } from '../contexts/RecentlyViewedContext';
import AssetSidebar from '../components/asset/AssetSidebar';
import BreadcrumbNavigation from '../components/common/BreadcrumbNavigation';
import AssetHeader from '../components/asset/AssetHeader';
import { AssetAudio } from '../components/asset';
import { formatCamelCase } from '../utils/stringUtils';
import { TruncatedTextWithTooltip } from '../components/common/TruncatedTextWithTooltip';
import { formatLocalDateTime } from '@/shared/utils/dateUtils';
import { SimpleTreeView } from '@mui/x-tree-view/SimpleTreeView';
import { TreeItem } from '@mui/x-tree-view/TreeItem';
import { Chip as MuiChip } from '@mui/material';
import { RelatedItemsView } from '../components/shared/RelatedItemsView';
import { AssetResponse } from '../api/types/asset.types';
import type { RelatedVersionsResponse } from '../api/hooks/useAssets';
import { formatFileSize } from '../utils/imageUtils';

// MUI Icons
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import CodeOutlinedIcon from '@mui/icons-material/CodeOutlined';
import LinkOutlinedIcon from '@mui/icons-material/LinkOutlined';
import SubtitlesOutlinedIcon from '@mui/icons-material/SubtitlesOutlined';

const outputFilters = {
    'ID3v2': ['Title', 'Artist', 'Album', 'Year', 'Genre', 'Track'],
    'MP3 Info': ['Bitrate', 'SampleRate', 'Channels', 'Duration'],
    'FLAC': ['StreamInfo', 'VorbisComment', 'Channels', 'BitsPerSample'],
    'WAV': ['Format', 'AudioFormat', 'NumChannels', 'SampleRate', 'ByteRate'],
    'Ogg Vorbis': ['Vendor', 'Comments', 'BitrateNominal', 'Version'],
    'Audio Metadata': ['Album', 'Artist', 'Composer', 'Genre', 'Year', 'TrackNumber'],
    'Technical': ['Format', 'Duration', 'BitRate', 'SampleRate', 'Channels'],
    'MusicBrainz': ['ReleaseID', 'ArtistID', 'ReleaseGroupID'],
    'Encoding': ['EncodedBy', 'EncoderSettings', 'EncodingTime'],
    'Rights': ['Copyright', 'License', 'Owner'],
    'IPTC': ['Headline', 'Byline', 'Credit', 'Caption', 'Source', 'Country'],
    'ICC': ['ProfileVersion', 'ProfileClass', 'ColorSpaceData', 'ProfileConnectionSpace', 'ProfileFileSignature', 'DeviceManufacturer', 'RenderingIntent', 'ProfileCreator', 'ProfileDescription'],
    'XMP': ['Creator', 'Title', 'Description', 'Rights'],
    'Maker Note': [],
    'User Comment': [],
    'IPTC Core': ['CreatorContactInfo', 'Scene'],
    'IPTC Extension': ['PersonInImage', 'LocationCreated'],
    'PLUS': ['LicenseID', 'ImageCreator', 'CopyrightOwner'],
    'Dublin Core': ['Format', 'Type', 'Identifier'],
    'XMP Media Management': ['DerivedFrom', 'DocumentID', 'InstanceID'],
    'Auxiliary': ['SerialNumber'],
    'XMP Dynamic Media': ['AudioSampleRate', 'AudioChannelType', 'Duration', 'StartTimeScale'],
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

// New component for audio metadata content with a grid layout like the screenshot
const AudioMetadataContent: React.FC<MetadataContentProps> = ({ data, depth = 0, showAll, category }) => {
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
                // Special case for Tags with Encoder
                if (key === 'Tags' && 'Encoder' in value) {
                    // Mark this as a parent with _PARENT_ prefix (for internal use)
                    result.push([`_PARENT_${key}`, '']);
                    
                    // Then add the Encoder with its value - using a more visible indent prefix
                    Object.entries(value).forEach(([subKey, subValue]) => {
                        result.push([`      ↳ ${subKey}`, subValue]);
                    });
                } else {
                    // Mark this as a parent with _PARENT_ prefix (for internal use)
                    result.push([`_PARENT_${key}`, '']);
                    
                    // Then add the subkeys with more pronounced indentation
                    Object.entries(value).forEach(([subKey, subValue]) => {
                        result.push([`      ↳ ${subKey}`, subValue]);
                    });
                }
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
                        <AudioMetadataContent data={item} depth={depth + 1} showAll={showAll} category={category} />
                    </ListItem>
                ))}
            </List>
        );
    } else if (typeof data === 'object' && data !== null) {
        let entries = Object.entries(data);
        const sortedEntries = sortEntries(entries);
        // Flatten nested metadata like Tags/Encoder
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
                    // because we want to ensure the child appears in the next row
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
                                        <AudioMetadataContent
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
    const metadata = assetData?.data?.asset?.Metadata?.CustomMetadata || {};
    const generalMetadata = metadata?.General || {};
    const audioMetadata = metadata?.Audio?.[0] || {};
    const fileSize = assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.StorageInfo?.PrimaryLocation?.FileInfo?.Size || 0;
    const format = assetData?.data?.asset?.DigitalSourceAsset?.MainRepresentation?.Format || 'Unknown';
    
    // Audio-specific metadata fields
    const duration = generalMetadata?.Duration || audioMetadata?.Duration || 'Unknown';
    const sampleRate = audioMetadata?.SampleRate || audioMetadata?.Samplerate || '44.1';
    const bitDepth = audioMetadata?.BitDepth || audioMetadata?.BitsPerSample || '16';
    const channels = audioMetadata?.Channels || audioMetadata?.AudioChannels || '2';
    const bitRate = audioMetadata?.Bitrate ? `${Math.round(audioMetadata.Bitrate / 1000)} kbps` : 'Unknown';
    const codec = audioMetadata?.CodecName || audioMetadata?.Format || 'Unknown';
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
                    <Typography sx={{ flex: 1, fontSize: '0.875rem' }}>{assetData?.data?.asset?.DigitalSourceAsset?.Type || 'Audio'}</Typography>
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
                    <Typography sx={{ width: '120px', color: 'text.secondary', fontSize: '0.875rem' }}>Sample Rate:</Typography>
                    <Typography sx={{ flex: 1, fontSize: '0.875rem' }}>{sampleRate} kHz</Typography>
                </Box>
                
                <Box sx={{ display: 'flex', mb: 1 }}>
                    <Typography sx={{ width: '120px', color: 'text.secondary', fontSize: '0.875rem' }}>Bit Depth:</Typography>
                    <Typography sx={{ flex: 1, fontSize: '0.875rem' }}>{bitDepth} bit</Typography>
                </Box>
                
                <Box sx={{ display: 'flex', mb: 1 }}>
                    <Typography sx={{ width: '120px', color: 'text.secondary', fontSize: '0.875rem' }}>Channels:</Typography>
                    <Typography sx={{ flex: 1, fontSize: '0.875rem' }}>{channels}</Typography>
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
                    {metadataFields.descriptive.find((item: any) => item.label === 'Description')?.value || 'No description available'}
                </Typography>
                
                <Box sx={{ 
                    display: 'flex', 
                    flexWrap: 'wrap', 
                    gap: 0.75
                }}>
                    {(metadataFields.descriptive.find((item: any) => item.label === 'Keywords')?.value || 'audio,sound')
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
            </Box>
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
        // Use AudioMetadataContent for audio-related categories and General category
        if (subCategory.category.toLowerCase().includes('audio') || 
            subCategory.category === 'General' ||
            subCategory.category.toLowerCase() === 'general') {
            return (
                <AudioMetadataContent
                    data={subCategory.data}
                    showAll={true}
                    category={subCategory.category}
                />
            );
        }
        
        // Use default MetadataContent for other categories
        return (
            <MetadataContent
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
                                    {/* Replace "CustomMetadata" with "Embedded Metadata" */}
                                    {parentAccordion.category === "CustomMetadata" 
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

const TranscriptionTab: React.FC = () => {
    const theme = useTheme();
    
    // Sample Amazon Transcribe data
    const transcriptionData = {
        jobName: "media-futures-podcast-transcription",
        accountId: "123456789012",
        results: {
            transcripts: [
                {
                    transcript: "Welcome to Media Futures Podcast. Today we're exploring three big questions facing the media and entertainment industry. First, how will streaming platforms evolve with market saturation? Second, what monetization strategies will prove sustainable? And finally, how is AI transforming creative workflows? Joining me are industry experts Sarah Chen, former Netflix executive, David Rodriguez from Universal Media, and AI specialist Dr. Michelle Wong."
                }
            ],
            items: [
                {
                    start_time: "0.00",
                    end_time: "3.45",
                    alternatives: [{ confidence: "0.98", content: "Welcome to Media Futures Podcast. Today we're exploring three big questions" }],
                    type: "pronunciation"
                },
                {
                    start_time: "3.46",
                    end_time: "6.70",
                    alternatives: [{ confidence: "0.96", content: "facing the media and entertainment industry." }],
                    type: "pronunciation"
                },
                {
                    start_time: "7.15",
                    end_time: "11.45",
                    alternatives: [{ confidence: "0.99", content: "First, how will streaming platforms evolve with market saturation?" }],
                    type: "pronunciation"
                },
                {
                    start_time: "12.23",
                    end_time: "16.82",
                    alternatives: [{ confidence: "0.95", content: "Second, what monetization strategies will prove sustainable?" }],
                    type: "pronunciation"
                },
                {
                    start_time: "17.32",
                    end_time: "21.78",
                    alternatives: [{ confidence: "0.97", content: "And finally, how is AI transforming creative workflows?" }],
                    type: "pronunciation"
                },
                {
                    start_time: "22.48",
                    end_time: "25.95",
                    alternatives: [{ confidence: "0.95", content: "Joining me are industry experts Sarah Chen" }],
                    type: "pronunciation"
                },
                {
                    start_time: "26.12",
                    end_time: "29.35",
                    alternatives: [{ confidence: "0.92", content: "former Netflix executive, David Rodriguez from Universal Media" }],
                    type: "pronunciation"
                },
                {
                    start_time: "29.68",
                    end_time: "32.43",
                    alternatives: [{ confidence: "0.94", content: "and AI specialist Dr. Michelle Wong." }],
                    type: "pronunciation"
                }
            ],
            status: "COMPLETED"
        }
    };

    return (
        <Box sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 600 }}>
                Audio Transcription
            </Typography>
            
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
                    {transcriptionData.results.transcripts[0].transcript}
                </Typography>
            </Paper>
            
            <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 600 }}>
                Time-Aligned Segments
            </Typography>
            
            <Paper elevation={0} sx={{ 
                backgroundColor: alpha(theme.palette.background.paper, 0.5),
                borderRadius: 1
            }}>
                {transcriptionData.results.items.map((item, index) => (
                    <Box 
                        key={index} 
                        sx={{ 
                            display: 'flex', 
                            p: 1.5, 
                            borderBottom: index < transcriptionData.results.items.length - 1 ? 
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
                        </Box>
                        <Box sx={{ pl: 2, flex: 1 }}>
                            <Typography variant="body2">
                                {item.alternatives[0].content}
                            </Typography>
                            {item.alternatives.length > 1 && (
                                <Box sx={{ mt: 1 }}>
                                    <Typography variant="caption" sx={{ color: theme.palette.text.secondary }}>
                                        Alternatives:
                                    </Typography>
                                    {item.alternatives.slice(1).map((alt, altIndex) => {
                                        const confidenceValue = Math.round(parseFloat(alt.confidence) * 100);
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
                        </Box>
                    </Box>
                ))}
            </Paper>
            
            <Box sx={{ mt: 3, display: 'flex', justifyContent: 'center' }}>
                <Button 
                    variant="outlined" 
                    startIcon={<SubtitlesOutlinedIcon />}
                    sx={{ mr: 2 }}
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

const AudioDetailContent: React.FC = () => {
    const { id } = useParams<{ id: string }>();
    const navigate = useNavigate();
    const location = useLocation();
    const { isExpanded, closeSidebar } = useRightSidebar();
    const { data: assetData, isLoading, error } = useAsset(id || '') as { data: AssetResponse | undefined; isLoading: boolean; error: any };
    const [activeTab, setActiveTab] = useState<string>('summary');
    const [relatedPage, setRelatedPage] = useState(1);
    const { data: relatedVersionsData, isLoading: isLoadingRelated } = useRelatedVersions(id || '', relatedPage);
    const [showHeader, setShowHeader] = useState(true);

    const [expandedMetadata, setExpandedMetadata] = useState<{ [key: string]: boolean }>({});
    const [comments, setComments] = useState([
        { user: "John Doe", avatar: "https://mui.com/static/videos/avatar/1.jpg", content: "Great audio quality!", timestamp: "2023-06-15 09:30:22" },
        { user: "Jane Smith", avatar: "https://mui.com/static/videos/avatar/2.jpg", content: "The mix is perfect", timestamp: "2023-06-15 10:15:43" },
        { user: "Mike Johnson", avatar: "https://mui.com/static/videos/avatar/3.jpg", content: "Can we adjust the levels?", timestamp: "2023-06-15 11:22:17" },
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
                { label: 'Title', value: 'Media Futures Podcast: Three Big Questions' },
                { label: 'Type', value: 'Audio' },
                { label: 'Duration', value: '42:18' }
            ],
            descriptive: [
                { label: 'Description', value: 'Industry experts discuss three fundamental questions facing the media and entertainment industry: the future of streaming platforms, content monetization strategies, and the impact of AI on creative workflows.' },
                { label: 'Keywords', value: 'podcast, media industry, streaming, monetization, AI, entertainment' },
                { label: 'Location', value: 'NAB 2025' }
            ],
            technical: [
                { label: 'Format', value: assetData.data.asset.DigitalSourceAsset.MainRepresentation.Format },
                { label: 'File Size', value: assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size },
                { label: 'Date Created', value: '2024-05-15' }
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
        { user: "John Doe", action: "Uploaded audio", timestamp: "2024-01-07 09:30:22" },
        { user: "AI Pipeline", action: "Generated metadata", timestamp: "2024-01-07 09:31:05" },
        { user: "Jane Smith", action: "Added tags", timestamp: "2024-01-07 10:15:43" }
    ];

    // Track this asset in recently viewed
    useTrackRecentlyViewed(
        assetData ? {
            id: assetData.data.asset.DigitalSourceAsset.MainRepresentation.ID,
            title: assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name,
            type: assetData.data.asset.DigitalSourceAsset.Type.toLowerCase() as "audio",
            path: `/audio/${assetData.data.asset.InventoryID}`,
            searchTerm: searchTerm,
            metadata: {
                duration: '42:18',
                fileSize: `${assetData.data.asset.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size} bytes`,
                creator: 'John Doe'
            }
        } : null
    );

    // Handle keyboard navigation for tabs
    const handleTabKeyDown = useCallback((event: React.KeyboardEvent) => {
        const tabs = ['summary', 'technical', 'descriptor', 'transcription', 'related'];
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
                        assetType="Audio"
                    />
                </Box>
            </Box>

            {/* Audio player section */}
            <Box sx={{ px: 3, pt: 0, pb: 3, height: '50vh', minHeight: '400px' }}>
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
                    <AssetAudio
                        src={proxyUrl}
                        alt={assetData.data.asset.DigitalSourceAsset.MainRepresentation.ID}
                    />
                </Paper>
            </Box>

            {/* Metadata section */}
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
                                value="descriptor"
                                label="Descriptor Metadata"
                                id="tab-descriptor"
                                aria-controls="tabpanel-descriptor"
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
                                outline: 'none',
                                borderRadius: 1,
                                backgroundColor: theme => alpha(theme.palette.background.paper, 0.5),
                                maxHeight: 'none',
                                overflow: 'visible'
                            }}
                            role="tabpanel"
                            id={`tabpanel-${activeTab}`}
                            aria-labelledby={`tab-${activeTab}`}
                            tabIndex={0}
                        >
                            {activeTab === 'summary' && <SummaryTab metadataFields={metadataFields} assetData={assetData} />}
                            {activeTab === 'technical' && <TechnicalMetadataTab metadataAccordions={metadataAccordions} />}
                            {activeTab === 'descriptor' && <DescriptorMetadataTab metadataFields={metadataFields} />}
                            {activeTab === 'transcription' && <TranscriptionTab />}
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
            />
        </Box>
    );
};

const AudioDetailPage: React.FC = () => {
    return (
        <RecentlyViewedProvider>
            <RightSidebarProvider>
                <AudioDetailContent />
            </RightSidebarProvider>
        </RecentlyViewedProvider>
    );
};

export default AudioDetailPage; 