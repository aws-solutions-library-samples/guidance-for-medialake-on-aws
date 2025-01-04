import React, { useState, useEffect } from 'react';
import { Box, Typography, List, ListItemText, ListItemIcon, Checkbox, ListItemButton, Divider, Collapse, LinearProgress, Paper } from '@mui/material';
import { Button } from '@/components/common';
import ExpandLess from '@mui/icons-material/ExpandLess';
import ExpandMore from '@mui/icons-material/ExpandMore';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import SearchOffIcon from '@mui/icons-material/SearchOff';
import VideoResults from '@/components/search/VideoResults';
import ImageResults from '@/components/search/ImageResults';
import AudioResults from '@/components/search/AudioResults';
import { useLocation, useSearchParams, useNavigate } from 'react-router-dom';
import { useSearch } from '@/api/hooks/useSearch';
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

    const imageResults = searchResults?.data?.results?.filter(item => item.DigitalSourceAsset.Type === 'Image') || [];

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
            {filterBarExpanded && <Divider />}
        </>
    );

    return (
        <Box sx={{
            display: 'flex',
            minHeight: '100%',
            bgcolor: '#fff',
            position: 'relative',
            overflow: 'auto',
            paddingBottom: '120px', // Increase padding for pagination controls
            marginBottom: '-56px' // Negative margin to prevent double spacing
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
                pb: 12, // Increase bottom padding
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
                minHeight: 0 // Allow content to shrink
            }}>
                {searchResults?.data?.searchMetadata?.totalResults === 0 && currentQuery && (
                    <Box
                        sx={{
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            minHeight: '50vh',
                            textAlign: 'center',
                            gap: 2
                        }}
                    >
                        <Paper
                            elevation={0}
                            sx={{
                                p: 4,
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center',
                                gap: 2,
                                bgcolor: '#fff',
                                borderRadius: 2
                            }}
                        >
                            <SearchOffIcon
                                sx={{
                                    fontSize: 64,
                                    color: 'text.secondary',
                                    mb: 2
                                }}
                            />
                            <Typography variant="h5" color="text.primary" gutterBottom>
                                No results found
                            </Typography>
                            <Typography variant="body1" color="text.secondary">
                                We couldn't find any matches for "{currentQuery}"
                            </Typography>
                            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                                Try adjusting your search or filters to find what you're looking for
                            </Typography>
                        </Paper>
                    </Box>
                )}

                {filters.mediaTypes.images && imageResults.length > 0 && searchResults?.data?.searchMetadata && (
                    <ImageResults
                        images={imageResults}
                        searchMetadata={{
                            totalResults: searchResults.data.searchMetadata.totalResults || 0,
                            page: currentPage,
                            pageSize: PAGE_SIZE,
                        }}
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
                bgcolor: '#fff',
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
                    <Button
                        variant="text"
                        onClick={() => setFilterBarExpanded(!filterBarExpanded)}
                        startIcon={
                            <ChevronRightIcon
                                sx={{
                                    transform: filterBarExpanded ? 'rotate(0deg)' : 'rotate(180deg)',
                                    transition: theme => theme.transitions.create('transform', {
                                        duration: theme.transitions.duration.shortest,
                                    }),
                                }}
                            />
                        }
                        sx={{ minWidth: 'unset', width: '40px', p: 0 }}
                    />
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
