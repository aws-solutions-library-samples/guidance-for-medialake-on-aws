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
import { alpha } from '@mui/material/styles';
import { Button } from '@/components/common';
import {
  Search as SearchIcon,
  CloudUpload as CloudUploadIcon,
  FilterList as FilterListIcon,
  Chat as ChatIcon,
  Notifications as NotificationsIcon,
  Psychology as PsychologyIcon
} from '@mui/icons-material';
import { useChat } from './contexts/ChatContext';
import { useNavigate, useLocation } from 'react-router-dom'; // <-- import useLocation
import { useTranslation } from 'react-i18next';
import { useTheme } from './hooks/useTheme';
import { useSidebar } from './contexts/SidebarContext';
import { useDirection } from './contexts/DirectionContext';
import { drawerWidth, collapsedDrawerWidth } from './constants';
import { S3UploaderModal } from './features/upload';
import { useFeatureFlag } from './contexts/FeatureFlagsContext';
import FilterModal from './components/search/FilterModal';
import { useFacetSearch } from './hooks/useFacetSearch';
import { NotificationCenter } from './components/NotificationCenter';

interface SearchTag {
  key: string;
  value: string;
}

function TopBar() {
  const muiTheme = useMuiTheme();
  const { theme } = useTheme();
  const { isCollapsed } = useSidebar();
  const navigate = useNavigate();
  const location = useLocation(); // <-- grab location
  const { t } = useTranslation();
  const { direction } = useDirection();
  const isRTL = direction === 'rtl';

  const [searchInput, setSearchInput] = useState('');
  const [searchTags, setSearchTags] = useState<SearchTag[]>([]);
  // Parse `semantic` from URL on initial render:
  const initialSemantic =
    new URLSearchParams(location.search).get('semantic') === 'true';
  const [isSemanticSearch, setIsSemanticSearch] = useState<boolean>(initialSemantic);

  const { filters, setFilters } = useFacetSearch();
  const [searchResults, setSearchResults] = useState<any>(null);
  const [searchBoxWidth, setSearchBoxWidth] = useState<number>(0);
  const searchBoxRef = useRef<HTMLDivElement>(null);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isFilterModalOpen, setIsFilterModalOpen] = useState(false);
  const isFileUploadEnabled = useFeatureFlag('file-upload-enabled', true);
  const isChatEnabled = useFeatureFlag('chat-enabled', true);
  const isNotificationEnabled = useFeatureFlag('notification-enabled', true);
  const { toggleChat, isOpen: isChatOpen } = useChat();

  // Add state for clipType
  const [clipType, setClipType] = useState<'clip' | 'full'>('clip');

  // Initialize clipType from URL parameters
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const clipTypeParam = params.get('clipType') as 'clip' | 'full';
    if (clipTypeParam && (clipTypeParam === 'clip' || clipTypeParam === 'full')) {
      setClipType(clipTypeParam);
    }
  }, [location.search]);

  // Update URL when clipType changes
  useEffect(() => {
    if (isSemanticSearch) {
      const params = new URLSearchParams(location.search);
      params.set('clipType', clipType);
      navigate({
        pathname: location.pathname,
        search: params.toString()
      }, { replace: true });
    }
  }, [clipType, isSemanticSearch, location.pathname, location.search, navigate]);

  // Whenever the URL's `semantic` param changes (e.g. on browser refresh),
  // make sure `isSemanticSearch` reflects that:
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const semanticParam = params.get('semantic') === 'true';
    setIsSemanticSearch(semanticParam);
  }, [location.search]);

  const getSearchQuery = useCallback(() => {
    const tagPart = searchTags
      .map(tag => `${tag.key}: ${tag.value}`)
      .join(' ');
    return `${tagPart}${tagPart && searchInput ? ' ' : ''}${searchInput}`.trim();
  }, [searchTags, searchInput]);

  const handleApplyFilters = (newFilters: any) => {
    setFilters(newFilters);
    const searchQuery = getSearchQuery();
    let search = `?q=${encodeURIComponent(searchQuery)}&semantic=${isSemanticSearch}`;
    if (isSemanticSearch) search += `&clipType=${clipType}`;
    if (newFilters.type) search += `&type=${encodeURIComponent(newFilters.type)}`;
    if (newFilters.extension) search += `&extension=${encodeURIComponent(newFilters.extension)}`;
    if (newFilters.LargerThan) search += `&LargerThan=${newFilters.LargerThan}`;
    if (newFilters.asset_size_lte) search += `&asset_size_lte=${newFilters.asset_size_lte}`;
    if (newFilters.asset_size_gte) search += `&asset_size_gte=${newFilters.asset_size_gte}`;
    if (newFilters.ingested_date_lte) search += `&ingested_date_lte=${encodeURIComponent(newFilters.ingested_date_lte)}`;
    if (newFilters.ingested_date_gte) search += `&ingested_date_gte=${encodeURIComponent(newFilters.ingested_date_gte)}`;
    if (newFilters.filename) search += `&filename=${encodeURIComponent(newFilters.filename)}`;
    navigate({
      pathname: '/search',
      search
    });
  };

  // Measure search box width
  useEffect(() => {
    const updateWidth = () => {
      if (searchBoxRef.current) {
        const width = searchBoxRef.current.offsetWidth;
        setSearchBoxWidth(width);
        console.log('Search box width measured:', width);
      }
    };

    // Initial measurement after a short delay
    setTimeout(updateWidth, 100);
    window.addEventListener('resize', updateWidth);
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
          console.error(
            'Error parsing search results from session storage',
            e
          );
        }
      }
    };
    handleStorageChange();
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

  const handleOpenFilterModal = () => {
    setIsFilterModalOpen(true);
  };

  const handleCloseFilterModal = () => {
    setIsFilterModalOpen(false);
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
        let search = `?q=${encodeURIComponent(searchQuery)}&semantic=${isSemanticSearch}`;
        if (isSemanticSearch) search += `&clipType=${clipType}`;
        navigate({
          pathname: '/search',
          search
        });
        return true;
      }
    }
    return false;
  };

  const handleSearchInputChange = (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const value = event.target.value;
    setSearchInput(value);

    if (value.endsWith(' ') && value.includes(':')) {
      const potentialTag = value.trim();
      if (createTagFromInput(potentialTag)) {
        return;
      }
    }

    // Remove automatic search - only search when button is clicked or Enter is pressed
    // if (!value.includes(':')) {
    //   const currentQuery = value.trim()
    //     ? `${searchTags
    //         .map(tag => `${tag.key}: ${tag.value}`)
    //         .join(' ')}${searchTags.length > 0 ? ' ' : ''}${value}`
    //     : searchTags.map(tag => `${tag.key}: ${tag.value}`).join(' ');
    //   // debouncedSearch(currentQuery);
    // }
  };

  const handleSearchKeyPress = (
    event: React.KeyboardEvent
  ) => {
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
      let search = `?q=${encodeURIComponent(searchQuery)}&semantic=${isSemanticSearch}`;
      if (isSemanticSearch) search += `&clipType=${clipType}`;
      navigate({
        pathname: '/search',
        search
      });
    }
  };

  const handleDeleteTag = (tagToDelete: SearchTag) => {
    setSearchTags(prev => {
      const newTags = prev.filter(
        tag =>
          !(
            tag.key === tagToDelete.key &&
            tag.value === tagToDelete.value
          )
      );
      const searchQuery = newTags
        .map(tag => `${tag.key}: ${tag.value}`)
        .join(' ');
      let search = `?q=${encodeURIComponent(searchQuery)}&semantic=${isSemanticSearch}`;
      if (isSemanticSearch) search += `&clipType=${clipType}`;
      navigate({
        pathname: '/search',
        search
      });
      return newTags;
    });
  };

  // Updated to handle both switch and icon button clicks
  const handleSemanticSearchToggle = () => {
    // Compute the new value
    const newSemantic = !isSemanticSearch;
    // Build the new search params
    const params = new URLSearchParams(location.search);
    params.set('semantic', newSemantic.toString());
    if (newSemantic) {
      params.set('clipType', clipType);
    } else {
      params.delete('clipType');
    }
    navigate({
      pathname: location.pathname,
      search: params.toString()
    });
    // Do NOT call setIsSemanticSearch here; let the useEffect handle it
  };

  const handleUploadComplete = (files: any[]) => {
    console.log('Upload completed:', files);
    handleCloseUploadModal();
    // Add any feedback if needed
  };

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        width: '100%',
        bgcolor: 'transparent',
        justifyContent: 'space-between',
        paddingRight: 0
      }}
    >
      {/* Search area container */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '100%',
          position: 'relative',
          mr: 2
        }}
      >
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
                color: muiTheme.palette.primary.contrastText
              }
            }}
          />
        ))}

        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '100%',
            maxWidth: '700px',
            mx: 'auto'
          }}
        >
          <Box
            ref={searchBoxRef}
            sx={{
              display: 'flex',
              alignItems: 'center',
              backgroundColor:
                theme === 'dark'
                  ? 'rgba(255,255,255,0.1)'
                  : 'rgba(0,0,0,0.04)',
              borderRadius: '24px',
              padding: '8px 16px',
              width: '100%',
              flexDirection: isRTL ? 'row-reverse' : 'row',
              boxShadow:
                theme === 'dark'
                  ? '0 2px 5px rgba(0,0,0,0.2)'
                  : 'none',
              position: 'relative',
            }}
          >
            {/* Clip/Full Toggle - inside the input, far left */}
            {isSemanticSearch && (
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  bgcolor: theme === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.03)',
                  borderRadius: '20px',
                  p: '2px',
                  mr: 1,
                  width: 140,
                  height: '36px',
                  position: 'relative',
                }}
              >
                <Box
                  sx={{
                    position: 'absolute',
                    top: 2,
                    left: clipType === 'clip' ? 2 : '50%',
                    width: '50%',
                    height: '32px',
                    bgcolor: muiTheme.palette.primary.light,
                    borderRadius: '16px',
                    transition: 'left 0.2s',
                    zIndex: 1,
                  }}
                />
                <Box
                  onClick={() => setClipType('clip')}
                  sx={{
                    flex: 1,
                    zIndex: 2,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: 'pointer',
                    color: clipType === 'clip' ? muiTheme.palette.primary.main : muiTheme.palette.text.secondary,
                    fontWeight: 600,
                    fontSize: '1rem',
                    userSelect: 'none',
                    height: '32px',
                  }}
                >
                  Clip
                </Box>
                <Box
                  onClick={() => setClipType('full')}
                  sx={{
                    flex: 1,
                    zIndex: 2,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: 'pointer',
                    color: clipType === 'full' ? muiTheme.palette.primary.main : muiTheme.palette.text.secondary,
                    fontWeight: 600,
                    fontSize: '1rem',
                    userSelect: 'none',
                    height: '32px',
                  }}
                >
                  Full
                </Box>
              </Box>
            )}
            {/* Search Icon */}
            <Box sx={{ display: 'flex', alignItems: 'center', mr: isSemanticSearch ? 1 : 1.5 }}>
              <SearchIcon
                sx={{
                  color:
                    theme === 'dark'
                      ? 'rgba(255,255,255,0.7)'
                      : 'text.secondary',
                  fontSize: '20px',
                  transition: 'margin 0.2s',
                }}
              />
            </Box>
            <InputBase
              placeholder={t('search.assets', 'Search assets...')}
              value={searchInput}
              onChange={handleSearchInputChange}
              onKeyUp={handleSearchKeyPress}
              fullWidth
              sx={{
                textAlign: isRTL ? 'right' : 'left',
                fontSize: '16px',
                color:
                  theme === 'dark'
                    ? 'white'
                    : muiTheme.palette.text.primary,
                '& input': {
                  padding: '6px 0',
                  '&::placeholder': {
                    color:
                      theme === 'dark'
                        ? 'rgba(255,255,255,0.7)'
                        : 'inherit',
                    opacity: 1,
                  },
                  paddingLeft: isSemanticSearch ? '0px' : '8px',
                  transition: 'padding 0.2s',
                }
              }}
            />

            {/* Filter Button */}
            <IconButton
              size="small"
              onClick={handleOpenFilterModal}
              sx={{
                color:
                  Object.keys(filters).length > 0
                    ? muiTheme.palette.primary.main
                    : theme === 'dark'
                    ? 'rgba(255,255,255,0.5)'
                    : 'rgba(0,0,0,0.4)',
                position: 'relative',
                '&:hover': {
                  backgroundColor: 'transparent',
                  color:
                    Object.keys(filters).length > 0
                      ? muiTheme.palette.primary.dark
                      : theme === 'dark'
                      ? 'rgba(255,255,255,0.7)'
                      : 'rgba(0,0,0,0.6)'
                },
                mr: 1
              }}
              title={t('search.filters.title', 'Filter Results')}
            >
              <FilterListIcon />
              {Object.keys(filters).length > 0 && (
                <Box
                  sx={{
                    position: 'absolute',
                    top: -2,
                    right: -2,
                    backgroundColor: muiTheme.palette.primary.main,
                    color: muiTheme.palette.primary.contrastText,
                    borderRadius: '50%',
                    width: 16,
                    height: 16,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.75rem',
                    fontWeight: 'bold'
                  }}
                >
                  {Object.keys(filters).length}
                </Box>
              )}
            </IconButton>
          </Box>

          {/* Search Button */}
          <Button
            variant="contained"
            onClick={handleSearchSubmit}
            sx={{
              minWidth: '80px',
              [isRTL ? 'mr' : 'ml']: 2,
              borderRadius: '20px',
              height: '40px'
            }}
          >
            {t('common.search')}
          </Button>

          {/* Semantic Search Button */}
          <Button
            variant={isSemanticSearch ? 'contained' : 'outlined'}
            onClick={handleSemanticSearchToggle}
            sx={{
              minWidth: '100px',
              [isRTL ? 'mr' : 'ml']: 2,
              borderRadius: '20px',
              height: '40px',
              color: isSemanticSearch
                ? muiTheme.palette.primary.contrastText
                : theme === 'dark'
                ? 'rgba(255,255,255,0.7)'
                : 'text.secondary',
              backgroundColor: isSemanticSearch
                ? muiTheme.palette.primary.main
                : 'transparent',
              borderColor: isSemanticSearch
                ? muiTheme.palette.primary.main
                : theme === 'dark'
                ? 'rgba(255,255,255,0.3)'
                : 'rgba(0,0,0,0.23)',
              transition: theme =>
                theme.transitions.create(
                  ['color', 'background-color', 'border-color', 'transform'],
                  {
                    duration: theme.transitions.duration.short
                  }
                ),
              '&:hover': {
                backgroundColor: isSemanticSearch
                  ? muiTheme.palette.primary.dark
                  : theme === 'dark'
                  ? 'rgba(255,255,255,0.08)'
                  : 'rgba(0,0,0,0.04)',
                transform: 'scale(1.02)'
              },
              '&:focus': {
                outline: `2px solid ${
                  isSemanticSearch
                    ? muiTheme.palette.primary.main
                    : 'rgba(0,0,0,0.2)'
                }`,
                outlineOffset: '2px'
              },
              boxShadow: isSemanticSearch
                ? `0 0 8px ${alpha(
                    muiTheme.palette.primary.main,
                    0.4
                  )}`
                : 'none'
            }}
            title={
              isSemanticSearch
                ? t('search.semantic.disable', 'Disable semantic search')
                : t('search.semantic.enable', 'Enable semantic search')
            }
            aria-pressed={isSemanticSearch}
          >
            {t('search.semantic.label', 'Semantic')}
          </Button>
        </Box>
      </Box>

      {/* Right-aligned icons */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          mr: 2
        }}
      >
        {/* Upload Button */}
        {isFileUploadEnabled && (
          <IconButton
            size="small"
            onClick={handleOpenUploadModal}
            sx={{
              color:
                theme === 'dark'
                  ? 'rgba(255,255,255,0.7)'
                  : 'text.secondary',
              backgroundColor:
                theme === 'dark'
                  ? 'rgba(255,255,255,0.1)'
                  : 'rgba(0,0,0,0.04)',
              borderRadius: '8px',
              padding: '8px',
              '&:hover': {
                backgroundColor:
                  theme === 'dark'
                    ? 'rgba(255,255,255,0.2)'
                    : 'rgba(0,0,0,0.08)'
              }
            }}
          >
            <CloudUploadIcon />
          </IconButton>
        )}

        {/* Notification Center */}
        {isNotificationEnabled && <NotificationCenter />}

        {/* Chat Icon Button */}
        {isChatEnabled && (
          <IconButton
            size="small"
            onClick={toggleChat}
            sx={{
              color: isChatOpen
                ? muiTheme.palette.primary.main
                : theme === 'dark'
                ? 'rgba(255,255,255,0.7)'
                : 'text.secondary',
              backgroundColor: isChatOpen
                ? alpha(muiTheme.palette.primary.main, 0.1)
                : theme === 'dark'
                ? 'rgba(255,255,255,0.1)'
                : 'rgba(0,0,0,0.04)',
              borderRadius: '8px',
              padding: '8px',
              transition: theme =>
                theme.transitions.create(
                  ['color', 'background-color'],
                  {
                    duration: theme.transitions.duration.short
                  }
                ),
              '&:hover': {
                backgroundColor: isChatOpen
                  ? alpha(muiTheme.palette.primary.main, 0.2)
                  : theme === 'dark'
                  ? 'rgba(255,255,255,0.2)'
                  : 'rgba(0,0,0,0.08)'
              }
            }}
          >
            <ChatIcon />
          </IconButton>
        )}
      </Box>

      {/* Upload Modal */}
      {isFileUploadEnabled && (
        <S3UploaderModal
          open={isUploadModalOpen}
          onClose={handleCloseUploadModal}
          onUploadComplete={handleUploadComplete}
          title={t('upload.title', 'Upload Media Files')}
          description={t(
            'upload.description',
            'Select an S3 connector and upload your media files. Only audio, video, HLS, and MPEG-DASH formats are supported.'
          )}
        />
      )}

      {/* Filter Modal */}
      <FilterModal
        open={isFilterModalOpen}
        onClose={handleCloseFilterModal}
        onApplyFilters={handleApplyFilters}
        activeFilters={filters}
        facetCounts={searchResults?.data?.searchMetadata?.facets}
      />
    </Box>
  );
}

export default TopBar;
