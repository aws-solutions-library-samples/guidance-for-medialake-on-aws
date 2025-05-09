import React, { useState, useCallback, useEffect, useRef } from 'react';
import {
    Box,
    useTheme as useMuiTheme,
    InputBase,
    Stack,
    Chip,
    IconButton,
    FormControlLabel,
    Switch,
    Typography,
    Paper
} from '@mui/material';
import { Button } from '@/components/common';
import {
    Search as SearchIcon,
    CloudUpload as CloudUploadIcon,
    Translate as TranslateIcon,
    Language as LanguageIcon
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import debounce from 'lodash/debounce';
import { useTranslation } from 'react-i18next';
import { useTheme } from './hooks/useTheme';
import { useSidebar } from './contexts/SidebarContext';
import { useDirection } from './contexts/DirectionContext';
import { drawerWidth, collapsedDrawerWidth } from './constants';
import { S3UploaderModal } from './features/upload';
import { useFeatureFlag } from './contexts/FeatureFlagsContext';
import FacetSearch from './components/search/FacetSearch';
import { useFacetSearch } from './hooks/useFacetSearch';

interface SearchTag {
    key: string;
    value: string;
}

function TopBar() {
    const muiTheme = useMuiTheme();
    const { theme } = useTheme();
    const { isCollapsed } = useSidebar();
    const navigate = useNavigate();
    const { t } = useTranslation();
    const { direction } = useDirection();
    const isRTL = direction === 'rtl';
    const [searchInput, setSearchInput] = useState('');
    const [searchTags, setSearchTags] = useState<SearchTag[]>([]);
    const [isSemanticSearch, setIsSemanticSearch] = useState(false);
    const { filters, setFilters } = useFacetSearch();
    const [searchResults, setSearchResults] = useState<any>(null);
    const [searchBoxWidth, setSearchBoxWidth] = useState<number>(0);
    const searchBoxRef = useRef<HTMLDivElement>(null);
    const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
    const isFileUploadEnabled = useFeatureFlag('file-upload-enabled', true);

    const getSearchQuery = useCallback(() => {
        const tagPart = searchTags.map(tag => `${tag.key}: ${tag.value}`).join(' ');
        return `${tagPart}${tagPart && searchInput ? ' ' : ''}${searchInput}`.trim();
    }, [searchTags, searchInput]);

    const debouncedSearch = useCallback(
        debounce((query: string) => {
            if (query.trim()) {
                navigate('/search', { state: { query, isSemantic: isSemanticSearch } });
            }
        }, 500),
        [navigate, isSemanticSearch]
    );

    const handleApplyFilters = (newFilters: any) => {
        setFilters(newFilters);
        
        // Trigger search with the new filters
        const searchQuery = getSearchQuery();
        
        // Create URLSearchParams object for the query parameters
        const queryParams = new URLSearchParams();
        queryParams.append('q', searchQuery);
        queryParams.append('semantic', isSemanticSearch.toString());
        
        // Add facet parameters to the URL
        if (newFilters.type) queryParams.append('type', newFilters.type);
        if (newFilters.extension) queryParams.append('extension', newFilters.extension);
        if (newFilters.LargerThan) queryParams.append('LargerThan', newFilters.LargerThan.toString());
        if (newFilters.asset_size_lte) queryParams.append('asset_size_lte', newFilters.asset_size_lte.toString());
        if (newFilters.asset_size_gte) queryParams.append('asset_size_gte', newFilters.asset_size_gte.toString());
        if (newFilters.ingested_date_lte) queryParams.append('ingested_date_lte', newFilters.ingested_date_lte);
        if (newFilters.ingested_date_gte) queryParams.append('ingested_date_gte', newFilters.ingested_date_gte);
        if (newFilters.filename) queryParams.append('filename', newFilters.filename);
        
        // Navigate to search page with query parameters
        navigate({
            pathname: '/search',
            search: queryParams.toString()
        });
    };
    
    // Measure search box width
    useEffect(() => {
        const updateWidth = () => {
            if (searchBoxRef.current) {
                // Get the full width of the search box
                const width = searchBoxRef.current.offsetWidth;
                setSearchBoxWidth(width);
                
                // Log for debugging
                console.log('Search box width measured:', width);
            }
        };
        
        // Initial measurement after a short delay to ensure rendering is complete
        setTimeout(updateWidth, 100);
        
        // Re-measure on window resize
        window.addEventListener('resize', updateWidth);
        
        // Re-measure when the component is fully rendered
        const observer = new ResizeObserver(() => {
            updateWidth();
        });
        
        if (searchBoxRef.current) {
            observer.observe(searchBoxRef.current);
        }
        
        return () => {
            window.removeEventListener('resize', updateWidth);
            observer.disconnect();
        };
    }, []);
    
    // Handle search results from session storage
    useEffect(() => {
        const handleStorageChange = () => {
            const storedResults = sessionStorage.getItem('searchResults');
            if (storedResults) {
                try {
                    setSearchResults(JSON.parse(storedResults));
                } catch (e) {
                    console.error('Error parsing search results from session storage', e);
                }
            }
        };
        
        // Initial check
        handleStorageChange();
        
        // Listen for storage changes
        window.addEventListener('storage', handleStorageChange);
        
        return () => {
            window.removeEventListener('storage', handleStorageChange);
        };
    }, []);

    const handleOpenUploadModal = () => {
        setIsUploadModalOpen(true);
    };

    const handleCloseUploadModal = () => {
        setIsUploadModalOpen(false);
    };

    const createTagFromInput = (input: string): boolean => {
        if (input.includes(':')) {
            const [key, ...valueParts] = input.split(':');
            const value = valueParts.join(':').trim();

            if (key && value) {
                const newTag: SearchTag = {
                    key: key.trim(),
                    value: value
                };

                setSearchTags(prev => [...prev, newTag]);
                setSearchInput('');

                const searchQuery = getSearchQuery();
                navigate('/search', { state: { query: searchQuery, isSemantic: isSemanticSearch } });
                return true;
            }
        }
        return false;
    };

    const handleSearchInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const value = event.target.value;
        setSearchInput(value);

        if (value.endsWith(' ') && value.includes(':')) {
            const potentialTag = value.trim();
            if (createTagFromInput(potentialTag)) {
                return;
            }
        }

        if (!value.includes(':')) {
            const currentQuery = value.trim() ?
                `${searchTags.map(tag => `${tag.key}: ${tag.value}`).join(' ')}${searchTags.length > 0 ? ' ' : ''}${value}` :
                searchTags.map(tag => `${tag.key}: ${tag.value}`).join(' ');
            debouncedSearch(currentQuery);
        }
    };

    const handleSearchKeyPress = (event: React.KeyboardEvent) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            handleSearchSubmit();
        }
    };

    const handleSearchSubmit = () => {
        if (searchInput.includes(':')) {
            createTagFromInput(searchInput);
        } else if (searchInput.trim() || searchTags.length > 0) {
            const searchQuery = getSearchQuery();
            navigate('/search', { state: { query: searchQuery, isSemantic: isSemanticSearch } });
        }
    };

    const handleDeleteTag = (tagToDelete: SearchTag) => {
        setSearchTags(prev => {
            const newTags = prev.filter(tag =>
                !(tag.key === tagToDelete.key && tag.value === tagToDelete.value)
            );
            const searchQuery = newTags.map(tag => `${tag.key}: ${tag.value}`).join(' ');
            navigate('/search', { state: { query: searchQuery, isSemantic: isSemanticSearch } });
            return newTags;
        });
    };

    // Updated to handle both switch and icon button clicks
    const handleSemanticSearchToggle = (event: React.MouseEvent | React.ChangeEvent<HTMLInputElement>) => {
        if ('checked' in (event.target as HTMLInputElement)) {
            // Handle Switch component event
            setIsSemanticSearch((event.target as HTMLInputElement).checked);
        } else {
            // Handle IconButton click - toggle the current state
            setIsSemanticSearch(prevState => !prevState);
        }
    };

    const handleUploadComplete = (files: any[]) => {
        console.log('Upload completed:', files);
        handleCloseUploadModal();
        // You could add a notification or other feedback here
    };

    return (
        <Box sx={{ 
            display: 'flex',
            alignItems: 'center',
            width: '100%',
            bgcolor: 'transparent',
        }}>
            <Box sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                width: '100%',
                bgcolor: 'transparent',
            }}>
                {/* Upload Button - Only shown if file upload is enabled */}
                {isFileUploadEnabled && (
                    <IconButton
                        size="small"
                        onClick={handleOpenUploadModal}
                        sx={{
                            color: theme === 'dark' ? 'rgba(255,255,255,0.7)' : 'text.secondary',
                            backgroundColor: theme === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.04)',
                            borderRadius: '8px',
                            padding: '8px',
                            '&:hover': {
                                backgroundColor: theme === 'dark' ? 'rgba(255,255,255,0.2)' : 'rgba(0,0,0,0.08)',
                            }
                        }}
                    >
                        <CloudUploadIcon />
                    </IconButton>
                )}

                {/* Tags */}
                {searchTags.map((tag, index) => (
                    <Chip
                        key={index}
                        label={`${tag.key}: ${tag.value}`}
                        onDelete={() => handleDeleteTag(tag)}
                        size="small"
                        sx={{
                            backgroundColor: muiTheme.palette.primary.light,
                            color: muiTheme.palette.primary.contrastText,
                            '& .MuiChip-deleteIcon': {
                                color: muiTheme.palette.primary.contrastText,
                            },
                        }}
                    />
                ))}

                {/* Google-style Search Input with Filter Icon */}
                <Box
                    ref={searchBoxRef}
                    sx={{
                        display: 'flex',
                        alignItems: 'center',
                        backgroundColor: theme === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.04)',
                        borderRadius: '24px', // More rounded like Google search
                        padding: '8px 16px',
                        flex: 1,
                        maxWidth: '800px', // Wider search box
                        width: '100%',
                        flexDirection: isRTL ? 'row-reverse' : 'row',
                        boxShadow: theme === 'dark' ? '0 2px 5px rgba(0,0,0,0.2)' : 'none',
                    }}
                >
                    <SearchIcon sx={{
                        color: theme === 'dark' ? 'rgba(255,255,255,0.7)' : 'text.secondary',
                        [isRTL ? 'ml' : 'mr']: 1.5,
                        fontSize: '20px'
                    }} />
                    <InputBase
                        placeholder={t('common.search')}
                        value={searchInput}
                        onChange={handleSearchInputChange}
                        onKeyUp={handleSearchKeyPress}
                        fullWidth
                        sx={{
                            textAlign: isRTL ? 'right' : 'left',
                            fontSize: '16px',
                            color: theme === 'dark' ? 'white' : muiTheme.palette.text.primary,
                            '& input': {
                                padding: '6px 0',
                                '&::placeholder': {
                                    color: theme === 'dark' ? 'rgba(255,255,255,0.7)' : 'inherit',
                                    opacity: 1,
                                },
                            },
                        }}
                    />
                    
                    {/* Semantic Search Toggle as Icon Button */}
                    <IconButton
                        size="small"
                        onClick={(e) => handleSemanticSearchToggle(e)}
                        sx={{
                            color: isSemanticSearch
                                ? muiTheme.palette.primary.main
                                : theme === 'dark' ? 'rgba(255,255,255,0.5)' : 'rgba(0,0,0,0.4)',
                            '&:hover': {
                                backgroundColor: 'transparent',
                                color: isSemanticSearch
                                    ? muiTheme.palette.primary.dark
                                    : theme === 'dark' ? 'rgba(255,255,255,0.7)' : 'rgba(0,0,0,0.6)',
                            },
                            mr: 1
                        }}
                        title={isSemanticSearch
                            ? t('search.semantic.disable', 'Disable semantic search')
                            : t('search.semantic.enable', 'Enable semantic search')}
                    >
                        <TranslateIcon />
                    </IconButton>
                    
                    {/* Facet Search Component */}
                    <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        <FacetSearch
                            onApplyFilters={handleApplyFilters}
                            activeFilters={filters}
                            facetCounts={searchResults?.data?.searchMetadata?.facets}
                            searchBoxWidth={searchBoxWidth}
                        />
                    </Box>
                </Box>

                {/* Search Button - Now outside the search box */}
                <Button
                    variant="contained"
                    onClick={handleSearchSubmit}
                    sx={{
                        minWidth: '80px',
                        ml: 2,
                        borderRadius: '20px', // Rounded button to match search box
                        height: '40px'  // Match height with search box
                    }}
                >
                    {t('common.search')}
                </Button>
            </Box>

            {/* Upload Modal - Only rendered if file upload is enabled */}
            {isFileUploadEnabled && (
                <S3UploaderModal
                    open={isUploadModalOpen}
                    onClose={handleCloseUploadModal}
                    onUploadComplete={handleUploadComplete}
                    title={t('upload.title', 'Upload Media Files')}
                    description={t('upload.description', 'Select an S3 connector and upload your media files. Only audio, video, HLS, and MPEG-DASH formats are supported.')}
                />
            )}
        </Box>
    );
}

export default TopBar;
