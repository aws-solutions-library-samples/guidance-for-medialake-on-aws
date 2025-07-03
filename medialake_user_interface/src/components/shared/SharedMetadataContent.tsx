import React from 'react';
import {
    Box,
    Typography,
    List,
    ListItem,
    useTheme,
    alpha
} from '@mui/material';
import { formatCamelCase } from '../../utils/stringUtils';

// Consolidated output filters from all three pages
const outputFilters = {
    // Image-specific filters (from ImageDetailPage)
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
    'Interoperability': ['InteroperabilityIndex', 'InteroperabilityVersion'],
    
    // Audio-specific filters (from AudioDetailPage)
    'ID3v2': ['Title', 'Artist', 'Album', 'Year', 'Genre', 'Track'],
    'MP3 Info': ['Bitrate', 'SampleRate', 'Channels', 'Duration'],
    'FLAC': ['StreamInfo', 'VorbisComment', 'Channels', 'BitsPerSample'],
    'WAV': ['Format', 'AudioFormat', 'NumChannels', 'SampleRate', 'ByteRate'],
    'Ogg Vorbis': ['Vendor', 'Comments', 'BitrateNominal', 'Version'],
    'Audio Metadata': ['Album', 'Artist', 'Composer', 'Genre', 'Year', 'TrackNumber'],
    'Technical': ['Format', 'Duration', 'BitRate', 'SampleRate', 'Channels'],
    'MusicBrainz': ['ReleaseID', 'ArtistID', 'ReleaseGroupID'],
    'Encoding': ['EncodedBy', 'EncoderSettings', 'EncodingTime']
};

interface SharedMetadataContentProps {
    data: any;
    depth?: number;
    showAll: boolean;
    category?: string;
    mediaType?: 'image' | 'audio' | 'video';
}

const SharedMetadataContent: React.FC<SharedMetadataContentProps> = ({ 
    data, 
    depth = 0, 
    showAll, 
    category,
    mediaType = 'image'
}) => {
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
                        <SharedMetadataContent 
                            data={item} 
                            depth={depth + 1} 
                            showAll={showAll} 
                            category={category}
                            mediaType={mediaType}
                        />
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
                                        <SharedMetadataContent
                                            data={value}
                                            depth={depth + 1}
                                            showAll={showAll}
                                            category={category}
                                            mediaType={mediaType}
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

export default SharedMetadataContent;
export { outputFilters };