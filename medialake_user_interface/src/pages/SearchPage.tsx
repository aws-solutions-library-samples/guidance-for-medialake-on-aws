import React, { useState } from 'react';
import { Box, Typography, List, ListItem, ListItemText, ListItemIcon, Checkbox, ListItemButton, Divider, IconButton, Collapse } from '@mui/material';
import ExpandLess from '@mui/icons-material/ExpandLess';
import ExpandMore from '@mui/icons-material/ExpandMore';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import VideoResults from '../components/search/VideoResults';
import ImageResults from '../components/search/ImageResults';
import AudioResults from '../components/search/AudioResults';

// Mock data remains exactly the same
const mockVideos = [
    { src: 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4', id: 1, fileName: 'Big Buck Bunny', creationDate: '2023-05-01T12:00:00Z', description: 'A short animated film about a big rabbit' },
    { src: 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4', id: 2, fileName: 'Elephants Dream', creationDate: '2023-05-02T14:30:00Z', description: 'The first Blender Open Movie from 2006' },
    { src: 'http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4', id: 3, fileName: 'Sintel', creationDate: '2023-05-03T10:15:00Z', description: 'Third Blender Open Movie from 2010' },
];

const mockImages = [
    { src: 'https://images.unsplash.com/photo-1501785888041-af3ef285b470', id: 1, fileName: 'Mountain Lake', creationDate: '2023-05-10T09:15:00Z', description: 'A serene mountain lake view' },
    { src: 'https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05', id: 2, fileName: 'River Valley', creationDate: '2023-05-11T16:45:00Z', description: 'A beautiful river flowing through a valley' },
    { src: 'https://images.unsplash.com/photo-1511497584788-876760111969', id: 3, fileName: 'Misty Forest', creationDate: '2023-05-12T11:30:00Z', description: 'A mysterious misty forest landscape' },
];

const mockAudios = [
    { src: 'https://file-examples.com/wp-content/uploads/2017/11/file_example_MP3_700KB.mp3', id: 1, fileName: 'Sample Audio 1', creationDate: '2023-05-25T11:20:00Z', description: 'A sample audio file for testing' },
    { src: 'https://file-examples.com/wp-content/uploads/2017/11/file_example_MP3_1MG.mp3', id: 2, fileName: 'Sample Audio 2', creationDate: '2023-05-26T13:10:00Z', description: 'Another sample audio file for testing' },
];

const SearchPage: React.FC = () => {
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
                    py: 2,
                    px: filterBarExpanded ? 3 : 2,
                    minHeight: 64,
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
                            p: 1,
                            bgcolor: 'background.paper',
                            border: '1px solid',
                            borderColor: 'divider',
                            '&:hover': {
                                bgcolor: 'action.hover'
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
                {filters.mediaTypes.images && <ImageResults images={mockImages} />}
                {filters.mediaTypes.audio && <AudioResults audios={mockAudios} />}
            </Box>
        </Box>
    );
};

export default SearchPage;
