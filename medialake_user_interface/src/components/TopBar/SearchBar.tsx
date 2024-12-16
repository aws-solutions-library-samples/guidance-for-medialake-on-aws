// components/TopBar/SearchBar.tsx
import React from 'react';
import { TextField, Button, Box } from '@mui/material';
import { Search as SearchIcon } from '@mui/icons-material';

interface SearchBarProps {
    searchQuery: string;
    onSearchChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
    onSearchSubmit: () => void;
}

const SearchBar: React.FC<SearchBarProps> = ({
    searchQuery,
    onSearchChange,
    onSearchSubmit
}) => (
    <Box sx={{ display: 'flex', flexGrow: 1, mr: 2 }}>
        <TextField
            label="Search"
            variant="outlined"
            size="small"
            value={searchQuery}
            onChange={onSearchChange}
            onKeyDown={(e) => e.key === 'Enter' && onSearchSubmit()}
            // onKeyPress={(e) => e.key === 'Enter' && onSearchSubmit()}
            sx={{ flexGrow: 1, mr: 2, bgcolor: 'background.paper' }}
        />
        <Button
            variant="contained"
            startIcon={<SearchIcon />}
            onClick={onSearchSubmit}
        >
            Search
        </Button>
    </Box>
);

export default React.memo(SearchBar);
