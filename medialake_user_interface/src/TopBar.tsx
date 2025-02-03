import React, { useState, useCallback } from 'react';
import { Box, useTheme as useMuiTheme, InputBase, Chip } from '@mui/material';
import { Button } from '@/components/common';
import { Search as SearchIcon } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import debounce from 'lodash/debounce';
import { useTranslation } from 'react-i18next';
import { useTheme } from './hooks/useTheme';
import { useSidebar } from './contexts/SidebarContext';
import { drawerWidth, collapsedDrawerWidth } from './constants';

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
    const [searchInput, setSearchInput] = useState('');
    const [searchTags, setSearchTags] = useState<SearchTag[]>([]);

    const getSearchQuery = useCallback(() => {
        const tagPart = searchTags.map(tag => `${tag.key}: ${tag.value}`).join(' ');
        return `${tagPart}${tagPart && searchInput ? ' ' : ''}${searchInput}`.trim();
    }, [searchTags, searchInput]);

    const debouncedSearch = useCallback(
        debounce((query: string) => {
            if (query.trim()) {
                navigate('/search', { state: { query } });
            }
        }, 500),
        [navigate]
    );

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
                navigate('/search', { state: { query: searchQuery } });
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
            navigate('/search', { state: { query: searchQuery } });
        }
    };

    const handleDeleteTag = (tagToDelete: SearchTag) => {
        setSearchTags(prev => {
            const newTags = prev.filter(tag =>
                !(tag.key === tagToDelete.key && tag.value === tagToDelete.value)
            );
            const searchQuery = newTags.map(tag => `${tag.key}: ${tag.value}`).join(' ');
            navigate('/search', { state: { query: searchQuery } });
            return newTags;
        });
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

                {/* Search Input */}
                <Box sx={{
                    display: 'flex',
                    alignItems: 'center',
                    backgroundColor: theme === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.04)',
                    borderRadius: '8px',
                    padding: '4px 12px',
                    flex: 1,
                }}>
                    <SearchIcon sx={{
                        color: theme === 'dark' ? 'rgba(255,255,255,0.7)' : 'text.secondary',
                        mr: 1
                    }} />
                    <InputBase
                        placeholder={t('common.search')}
                        value={searchInput}
                        onChange={handleSearchInputChange}
                        onKeyUp={handleSearchKeyPress}
                        fullWidth
                        sx={{
                            fontSize: '14px',
                            color: theme === 'dark' ? 'white' : muiTheme.palette.text.primary,
                            '& input': {
                                padding: '4px 0',
                                '&::placeholder': {
                                    color: theme === 'dark' ? 'rgba(255,255,255,0.7)' : 'inherit',
                                    opacity: 1,
                                },
                            },
                        }}
                    />
                </Box>

                {/* Search Button */}
                <Button
                    variant="contained"
                    onClick={handleSearchSubmit}
                    sx={{ minWidth: '80px' }}
                >
                    {t('common.search')}
                </Button>
            </Box>
        </Box>
    );
}

export default TopBar;
