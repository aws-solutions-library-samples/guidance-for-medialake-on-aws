import React, { useState, useEffect } from 'react';
import { Box, Typography, List, ListItemText, ListItemIcon, Checkbox, ListItemButton, Divider, IconButton, Collapse, LinearProgress } from '@mui/material';
import ExpandLess from '@mui/icons-material/ExpandLess';
import ExpandMore from '@mui/icons-material/ExpandMore';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import VideoResults from '../components/search/VideoResults';
import ImageResults from '../components/search/ImageResults';
import AudioResults from '../components/search/AudioResults';
import { useLocation, useSearchParams, useNavigate } from 'react-router-dom';
import { useSearch } from '../api/hooks/useSearch';
import MenuIcon from '@mui/icons-material/Menu';

interface LocationState {
    query?: string;
}

const PAGE_SIZE = 20;

const SearchPage: React.FC = () => {
    const location = useLocation();
    const navigate = useNavigate();
    const { query } = (location.state as LocationState) || {};
    const [searchParams, setSearchParams] = useSearchParams();
    const currentPage = parseInt(searchParams.get('page') || '1', 10);
    const currentQuery = searchParams.get('q') || query || '';

    const {
        data: searchResults,
        isLoading,
        isFetching
    } = useSearch(currentQuery, {
        page: currentPage,
        pageSize: PAGE_SIZE
    });

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

    const [filterBarExpanded, setFilterBarExpanded] = useState(false);

    useEffect(() => {
        if (query && !searchParams.has('q')) {
            setSearchParams(prev => {
                const newParams = new URLSearchParams(prev);
                newParams.set('q', query);
                if (!prev.has('page')) {
                    newParams.set('page', '1');
                }
                return newParams;
            });
        }
    }, [query, searchParams, setSearchParams]);

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

    const handleSearch = (params: { page: number }) => {
        setSearchParams(prev => {
            const newParams = new URLSearchParams(prev);
            newParams.set('page', params.page.toString());
            if (currentQuery) {
                newParams.set('q', currentQuery);
            }
            return newParams;
        });
    };

    const renderFilterSection = (title: string, section: string, items: Record<string, boolean>) => (
        <>
            <ListItemButton
                onClick={() => handleSectionToggle(section)}
                sx={{
                    py: 1,
                    minHeight: 40,
                    px: filterBarExpanded ? 2 : 1,
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
                            fontSize: '0.875rem'
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
                                    pl: 3,
                                    py: 0.75,
                                    '&:hover': {
                                        bgcolor: 'action.hover'
                                    }
                                }}
                            >
                                <ListItemIcon sx={{ minWidth: 32 }}>
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
                                        sx: {
                                            fontWeight: value ? 500 : 400,
                                            fontSize: '0.8125rem'
                                        }
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
            {isFetching && (
                <LinearProgress
                    sx={{
                        position: 'fixed',
                        top: 0,
                        left: 0,
                        right: 0,
                        zIndex: 9999
                    }}
                />
            )}

            {/* Main Content */}
            <Box sx={{
                flexGrow: 1,
                px: 4,
                py: 4,
                display: 'flex',
                flexDirection: 'column',
                gap: 6
            }}>
                {filters.mediaTypes.images && imageResults.length > 0 && searchResults?.data?.searchMetadata && (
                    <ImageResults
                        images={imageResults}
                        searchMetadata={searchResults.data.searchMetadata}
                        onPageChange={(newPage) => handleSearch({ page: newPage })}
                    />
                )}
            </Box>

            {/* Filter Sidebar */}
            <Box sx={{
                width: filterBarExpanded ? 240 : 48,
                flexShrink: 0,
                borderLeft: '1px solid',
                borderColor: 'divider',
                transition: theme => theme.transitions.create(['width'], {
                    easing: theme.transitions.easing.sharp,
                    duration: theme.transitions.duration.enteringScreen,
                }),
                overflowX: 'hidden',
                bgcolor: 'background.default',
                position: 'fixed',
                top: 64,
                right: 0,
                height: 'calc(100vh - 64px)',
                display: 'flex',
                flexDirection: 'column',
                zIndex: 1000
            }}>
                <Box sx={{
                    display: 'flex',
                    justifyContent: filterBarExpanded ? 'flex-start' : 'center',
                    px: 1,
                    py: 2
                }}>
                    <IconButton
                        onClick={() => setFilterBarExpanded(!filterBarExpanded)}
                        sx={{
                            transform: filterBarExpanded ? 'rotate(0deg)' : 'rotate(180deg)',
                            transition: theme => theme.transitions.create('transform', {
                                duration: theme.transitions.duration.shortest,
                            }),
                        }}
                    >
                        <ChevronRightIcon />
                    </IconButton>
                </Box>

                <List component="nav" sx={{ width: '100%' }}>
                    {renderFilterSection('Media Types', 'mediaTypes', filters.mediaTypes)}
                    {renderFilterSection('Time Period', 'time', filters.time)}
                    {renderFilterSection('Status', 'status', filters.status)}
                </List>
            </Box>

            {/* Spacer to prevent content from going under the fixed sidebar */}
            <Box sx={{ width: filterBarExpanded ? 240 : 48, flexShrink: 0 }} />
        </Box>
    );
};

export default SearchPage;
