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
        pageSize: PAGE_SIZE
    });

    const imageResults = searchResults?.data?.results?.filter(item => item.DigitalSourceAsset.Type === 'Image') || [];
    const videoResults = searchResults?.data?.results?.filter(item => item.DigitalSourceAsset.Type === 'Video') || [];
    const audioResults = searchResults?.data?.results?.filter(item => item.DigitalSourceAsset.Type === 'Audio') || [];

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
