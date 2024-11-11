import React, { useState } from 'react';
import { Box, Typography, List, ListItemText, ListItemIcon, Checkbox, ListItemButton, Divider, IconButton, Collapse } from '@mui/material';
import ExpandLess from '@mui/icons-material/ExpandLess';
import ExpandMore from '@mui/icons-material/ExpandMore';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import VideoResults from '../components/search/VideoResults';
import ImageResults, { ImageItem } from '../components/search/ImageResults';
import AudioResults from '../components/search/AudioResults';
import { useLocation } from 'react-router-dom';
import { useSearch } from '../api/hooks/useSearch';

// Mock data for video and audio remains the same
const mockVideos = [
    { src: 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4', id: 1, fileName: 'Big Buck Bunny', creationDate: '2023-05-01T12:00:00Z', description: 'A short animated film about a big rabbit' },
    { src: 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4', id: 2, fileName: 'Elephants Dream', creationDate: '2023-05-02T14:30:00Z', description: 'The first Blender Open Movie from 2006' },
    { src: 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4', id: 3, fileName: 'Sintel', creationDate: '2023-05-03T10:15:00Z', description: 'A short animated film about a big rabbit' },
];

const mockAudios = [
    { src: 'https://file-examples.com/wp-content/uploads/2017/11/file_example_MP3_700KB.mp3', id: 1, fileName: 'Sample Audio 1', creationDate: '2023-05-25T11:20:00Z', description: 'A sample audio file for testing' },
    { src: 'https://file-examples.com/wp-content/uploads/2017/11/file_example_MP3_1MG.mp3', id: 2, fileName: 'Sample Audio 2', creationDate: '2023-05-26T13:10:00Z', description: 'Another sample audio file for testing' },
];

interface LocationState {
    query?: string;
}

interface SearchResponse {
    status: string;
    message: string;
    data: {
        searchMetadata: any;
        results: ImageItem[];
    };
}

const SearchPage: React.FC = () => {
    const location = useLocation();
    const { query } = (location.state as LocationState) || {};
    const { data: searchResults } = useSearch(query || '') as { data: SearchResponse | undefined };
    const imageResults = searchResults?.data?.results?.filter(item => item.assetType === 'Image') || [];

    const [filters, setFilters] = useState({
        mediaTypes: {
            videos: true,
            images: true,
            audio: true,
        },
        time: {
            recent: false,
            lastWeek: false,
            lastMonth: false,
            lastYear: false,
        },
        status: {
            favorites: false,
            archived: false,
            shared: false,
        }
    });

    const [expandedSections, setExpandedSections] = useState({
        mediaTypes: true,
        time: true,
        status: true,
    });

    const [filterBarExpanded, setFilterBarExpanded] = useState(true);

    const handleFilterChange = (section: string, filter: string) => {
        setFilters(prev => ({
            ...prev,
            [section]: {
                ...prev[section as keyof typeof prev],
                [filter]: !prev[section as keyof typeof prev][filter as keyof typeof prev[keyof typeof prev]]
            }
        }));
    };

    const handleSectionToggle = (section: string) => {
        setExpandedSections(prev => ({
            ...prev,
            [section]: !prev[section as keyof typeof prev]
        }));
    };

    const renderFilterSection = (title: string, section: string, items: Record<string, boolean>) => (
        <>
            <ListItemButton
                onClick={() => handleSectionToggle(section)}
                sx={{
                    py: 1.5,
                    minHeight: 48,
                    px: filterBarExpanded ? 2.5 : 1,
                    justifyContent: filterBarExpanded ? 'initial' : 'center',
                    '&:hover': {
                        bgcolor: 'action.hover'
                    }
                }}
            >
                {filterBarExpanded && (
                    <ListItemText
                        primary={title}
                        primaryTypographyProps={{
                            fontWeight: 600,
                            fontSize: '0.95rem'
                        }}
                    />
                )}
                {filterBarExpanded && (expandedSections[section as keyof typeof expandedSections] ? <ExpandLess /> : <ExpandMore />)}
            </ListItemButton>
            {filterBarExpanded && (
                <Collapse in={expandedSections[section as keyof typeof expandedSections]} timeout="auto">
                    <List component="div" disablePadding>
                        {Object.entries(items).map(([key, value]) => (
                            <ListItemButton
                                key={key}
                                onClick={() => handleFilterChange(section, key)}
                                sx={{
                                    pl: 4.5,
                                    py: 1,
                                    '&:hover': {
                                        bgcolor: 'action.hover'
                                    }
                                }}
                            >
                                <ListItemIcon sx={{ minWidth: 36 }}>
                                    <Checkbox
                                        edge="start"
                                        checked={value}
                                        tabIndex={-1}
                                        disableRipple
                                        size="small"
                                        sx={{
                                            color: 'primary.main',
                                            '&.Mui-checked': {
                                                color: 'primary.main'
                                            }
                                        }}
                                    />
                                </ListItemIcon>
                                <ListItemText
                                    primary={key.charAt(0).toUpperCase() + key.slice(1)}
                                    primaryTypographyProps={{
                                        variant: 'body2',
                                        sx: { fontWeight: value ? 500 : 400 }
                                    }}
                                />
                            </ListItemButton>
                        ))}
                    </List>
                </Collapse>
            )}
            <Divider />
        </>
    );

    return (
        <Box sx={{
            display: 'flex',
            minHeight: '100vh',
            bgcolor: 'background.paper'
        }}>
            {/* Filter Sidebar */}
            <Box sx={{
                width: filterBarExpanded ? 280 : 73,
                flexShrink: 0,
                borderRight: '1px solid',
                borderColor: 'divider',
                transition: theme => theme.transitions.create(['width'], {
                    easing: theme.transitions.easing.sharp,
                    duration: theme.transitions.duration.enteringScreen,
                }),
                overflowX: 'hidden',
                bgcolor: 'background.default',
                position: 'sticky',
                top: 0,
                height: '100vh',
                display: 'flex',
                flexDirection: 'column'
            }}>
                <Box sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: filterBarExpanded ? 'space-between' : 'center',
                    py: 1.5,
                    px: filterBarExpanded ? 2 : 1,
                    minHeight: 56,
                    borderBottom: '1px solid',
                    borderColor: 'divider'
                }}>
                    {filterBarExpanded && (
                        <Typography variant="h6" sx={{ fontWeight: 600 }}>
                            Filters
                        </Typography>
                    )}
                    <IconButton
                        onClick={() => setFilterBarExpanded(!filterBarExpanded)}
                        sx={{
                            width: 40,
                            height: 40,
                            p: 0,
                            bgcolor: 'background.paper',
                            border: '1px solid',
                            borderColor: 'divider',
                            borderRadius: '8px',
                            '&:hover': {
                                bgcolor: 'action.hover'
                            },
                            '& .MuiSvgIcon-root': {
                                fontSize: 20
                            }
                        }}
                    >
                        {filterBarExpanded ? <ChevronLeftIcon /> : <ChevronRightIcon />}
                    </IconButton>
                </Box>

                <List component="nav" sx={{ width: '100%', mt: 1 }}>
                    {renderFilterSection('Media Types', 'mediaTypes', filters.mediaTypes)}
                    {renderFilterSection('Time Period', 'time', filters.time)}
                    {renderFilterSection('Status', 'status', filters.status)}
                </List>
            </Box>

            {/* Main Content */}
            <Box sx={{
                flexGrow: 1,
                px: 4,
                py: 4,
                display: 'flex',
                flexDirection: 'column',
                gap: 6
            }}>
                <Typography
                    variant="h4"
                    component="h1"
                    sx={{
                        fontWeight: 600,
                        background: 'linear-gradient(45deg, #2196F3 30%, #21CBF3 90%)',
                        WebkitBackgroundClip: 'text',
                        WebkitTextFillColor: 'transparent',
                        mb: 2
                    }}
                >
                    Media Library
                </Typography>

                {filters.mediaTypes.videos && <VideoResults videos={mockVideos} />}
                {filters.mediaTypes.images && imageResults.length > 0 && (
                    <ImageResults images={imageResults} />
                )}
                {filters.mediaTypes.audio && <AudioResults audios={mockAudios} />}
            </Box>
        </Box>
    );
};

export default SearchPage;
