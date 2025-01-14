import React, { useState, useEffect } from 'react';
import { Box, Typography, LinearProgress, Paper } from '@mui/material';
import SearchOffIcon from '@mui/icons-material/SearchOff';
import { RightSidebar, RightSidebarProvider } from '../components/common/RightSidebar';
import SearchFilters from '../components/search/SearchFilters';
import ImageResults from '../components/search/ImageResults';
import VideoResults from '../components/search/VideoResults';
import AudioResults from '../components/search/AudioResults';
import { useLocation, useSearchParams } from 'react-router-dom';
import { useSearch } from '../api/hooks/useSearch';

interface LocationState {
    query?: string;
}

interface Filters {
    mediaTypes: {
        videos: boolean;
        images: boolean;
        audio: boolean;
    };
    time: {
        recent: boolean;
        lastWeek: boolean;
        lastMonth: boolean;
        lastYear: boolean;
    };
}

const PAGE_SIZE = 20;

const SearchPage: React.FC = () => {
    const location = useLocation();
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
        pageSize: PAGE_SIZE,
    });

    const [filters, setFilters] = useState<Filters>({
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
        // status: {
        //     favorites: false,
        //     archived: false,
        //     shared: false,
        // }
    });

    const filteredResults = searchResults?.data?.results?.filter(item => {
        const isImage = item.DigitalSourceAsset.Type === 'Image' && filters.mediaTypes.images;
        const isVideo = item.DigitalSourceAsset.Type === 'Video' && filters.mediaTypes.videos;
        const isAudio = item.DigitalSourceAsset.Type === 'Audio' && filters.mediaTypes.audio;

        // Time-based filtering
        const createdAt = new Date(item.DigitalSourceAsset.CreateDate);
        const now = new Date();
        const isRecent = filters.time.recent && (now.getTime() - createdAt.getTime() <= 24 * 60 * 60 * 1000);
        const isLastWeek = filters.time.lastWeek && (now.getTime() - createdAt.getTime() <= 7 * 24 * 60 * 60 * 1000);
        const isLastMonth = filters.time.lastMonth && (now.getTime() - createdAt.getTime() <= 30 * 24 * 60 * 60 * 1000);
        const isLastYear = filters.time.lastYear && (now.getTime() - createdAt.getTime() <= 365 * 24 * 60 * 60 * 1000);

        const passesTimeFilter = !filters.time.recent && !filters.time.lastWeek && !filters.time.lastMonth && !filters.time.lastYear ||
            isRecent || isLastWeek || isLastMonth || isLastYear;

        return (isImage || isVideo || isAudio) && passesTimeFilter;
    }) || [];

    const imageResults = filteredResults.filter(item => item.DigitalSourceAsset.Type === 'Image');
    const videoResults = filteredResults.filter(item => item.DigitalSourceAsset.Type === 'Video');
    const audioResults = filteredResults.filter(item => item.DigitalSourceAsset.Type === 'Audio');

    const [expandedSections, setExpandedSections] = useState({
        mediaTypes: true,
        time: true,
        status: true,
    });


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

    const handleFilterChange = (section: keyof Filters, filter: string) => {
        setFilters(prev => {
            const newFilters = { ...prev };
            if (section === 'time') {
                // Reset all time filters
                Object.keys(newFilters.time).forEach(key => {
                    newFilters.time[key as keyof typeof newFilters.time] = false;
                });
            }
            (newFilters[section] as any)[filter] = !(prev[section] as any)[filter];
            return newFilters;
        });
    };



    const handleSectionToggle = (section: string) => {
        setExpandedSections(prev => ({
            ...prev,
            [section]: !prev[section as keyof typeof prev]
        }));
    };

    const handleSearch = (params: { page: number }) => {
        let timeFilter = '';
        if (filters.time.recent) timeFilter = 'recent';
        if (filters.time.lastWeek) timeFilter = 'lastWeek';
        if (filters.time.lastMonth) timeFilter = 'lastMonth';
        if (filters.time.lastYear) timeFilter = 'lastYear';

        setSearchParams(prev => {
            const newParams = new URLSearchParams(prev);
            newParams.set('page', params.page.toString());
            if (currentQuery) {
                newParams.set('q', currentQuery);
            }
            if (timeFilter) {
                newParams.set('time', timeFilter);
            }
            return newParams;
        });
    };



    return (
        <RightSidebarProvider>
            <Box sx={{
                display: 'flex',
                minHeight: '100%',
                bgcolor: 'background.default',
                position: 'relative',
                overflow: 'auto'
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
                    gap: 6,
                    minHeight: 0,
                    marginBottom: 4
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
                                    bgcolor: 'background.paper',
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
                            searchTerm={currentQuery}
                        />
                    )}
                    {filters.mediaTypes.videos && videoResults.length > 0 && searchResults?.data?.searchMetadata && (
                        <VideoResults
                            videos={videoResults}
                            searchMetadata={{
                                totalResults: searchResults.data.searchMetadata.totalResults || 0,
                                page: currentPage,
                                pageSize: PAGE_SIZE,
                            }}
                            onPageChange={(newPage) => handleSearch({ page: newPage })}
                            searchTerm={currentQuery}
                        />
                    )}
                    {filters.mediaTypes.audio && audioResults.length > 0 && searchResults?.data?.searchMetadata && (
                        <AudioResults
                            audios={audioResults}
                            searchMetadata={{
                                totalResults: searchResults.data.searchMetadata.totalResults || 0,
                                page: currentPage,
                                pageSize: PAGE_SIZE,
                            }}
                            onPageChange={(newPage) => handleSearch({ page: newPage })}
                            searchTerm={currentQuery}
                        />
                    )}

                </Box>

                <RightSidebar>
                    <SearchFilters
                        filters={filters}
                        expandedSections={expandedSections}
                        onFilterChange={handleFilterChange}
                        onSectionToggle={handleSectionToggle}
                    />
                </RightSidebar>
            </Box>
        </RightSidebarProvider>
    );
};

export default SearchPage;
