import React, { useState } from 'react';
import {
    AppBar,
    Toolbar,
    TextField,
    Button,
    Popover,
    Box,
    Typography,
    Checkbox,
    FormControlLabel,
    Switch,
    IconButton,
    Grid,
} from '@mui/material';
import { Search as SearchIcon, FilterList as FilterListIcon, Close as CloseIcon, Send as SendIcon } from '@mui/icons-material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { useNavigate } from 'react-router-dom';

interface FilterOptions {
    creationDate: {
        enabled: boolean;
        before: Date | null;
        after: Date | null;
    };
    media: {
        enabled: boolean;
        video: { types: { [key: string]: boolean } };
        images: { types: { [key: string]: boolean } };
        audio: { types: { [key: string]: boolean } };
    };
    metadata: {
        enabled: boolean;
        title: { types: { [key: string]: boolean } };
        rights: { types: { [key: string]: boolean } };
    };
}

interface ChatMessage {
    text: string;
    sender: 'user' | 'bot';
}

function TopBar() {
    const [searchQuery, setSearchQuery] = useState('');
    const [filterAnchorEl, setFilterAnchorEl] = useState<HTMLElement | null>(null);
    const [filterOptions, setFilterOptions] = useState<FilterOptions>({
        creationDate: {
            enabled: false,
            before: null,
            after: null,
        },
        media: {
            enabled: true,
            video: { types: { mp4: false, avi: false, mov: false } },
            images: { types: { jpg: false, png: false, gif: false } },
            audio: { types: { mp3: false, wav: false, ogg: false } },
        },
        metadata: {
            enabled: true,
            title: { types: { theatrical: false, episodic: false } },
            rights: { types: { acquisition: false, distribution: false } },
        },
    });
    const navigate = useNavigate();
    const [chatVisible, setChatVisible] = useState(false);
    const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
    const [chatInput, setChatInput] = useState('');

    const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setSearchQuery(event.target.value);
    };

    const handleFilterClick = (event: React.MouseEvent<HTMLElement>) => {
        setFilterAnchorEl(event.currentTarget);
    };

    const handleFilterClose = () => {
        setFilterAnchorEl(null);
    };

    const handleCheckboxChange = (category: keyof FilterOptions, subcategory: string, option: string) => (event: React.ChangeEvent<HTMLInputElement>) => {
        setFilterOptions((prevState) => ({
            ...prevState,
            [category]: {
                ...prevState[category],
                [subcategory]: {
                    ...prevState[category][subcategory],
                    types: {
                        ...prevState[category][subcategory].types,
                        [option]: event.target.checked,
                    },
                },
            },
        }));
    };

    const handleSectionToggle = (category: keyof FilterOptions) => (event: React.ChangeEvent<HTMLInputElement>) => {
        setFilterOptions((prevState) => ({
            ...prevState,
            [category]: {
                ...prevState[category],
                enabled: event.target.checked,
            },
        }));
    };

    const handleDateChange = (type: 'before' | 'after') => (date: Date | null) => {
        setFilterOptions((prevState) => ({
            ...prevState,
            creationDate: {
                ...prevState.creationDate,
                [type]: date,
            },
        }));
    };

    const handleSearchSubmit = () => {
        console.log('Search query:', searchQuery);
        console.log('Selected filters:', filterOptions);
        handleFilterClose();
    };

    const renderCheckboxes = (category: keyof FilterOptions, subcategory: string) => {
        return Object.keys(filterOptions[category][subcategory].types).map((option) => (
            <FormControlLabel
                key={option}
                control={
                    <Checkbox
                        checked={filterOptions[category][subcategory].types[option]}
                        onChange={handleCheckboxChange(category, subcategory, option)}
                        name={option}
                        size="small"
                    />
                }
                label={option.toUpperCase()}
            />
        ));
    };

    const renderMediaContent = () => (
        <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle1" gutterBottom>
                Media
            </Typography>
            {Object.keys(filterOptions.media)
                .filter((subcategory) => subcategory !== 'enabled')
                .map((subcategory) => (
                    <Box key={subcategory} sx={{ mb: 1 }}>
                        <Typography variant="subtitle2" gutterBottom>
                            {subcategory.charAt(0).toUpperCase() + subcategory.slice(1)}
                        </Typography>
                        <Grid container>{renderCheckboxes('media', subcategory)}</Grid>
                    </Box>
                ))}
        </Box>
    );

    const renderMetadataContent = () => (
        <Box>
            <Typography variant="subtitle1" gutterBottom>
                Metadata
            </Typography>
            {Object.keys(filterOptions.metadata)
                .filter((subcategory) => subcategory !== 'enabled')
                .map((subcategory) => (
                    <Box key={subcategory} sx={{ mb: 1 }}>
                        <Typography variant="subtitle2" gutterBottom>
                            {subcategory.charAt(0).toUpperCase() + subcategory.slice(1)}
                        </Typography>
                        <Grid container>{renderCheckboxes('metadata', subcategory)}</Grid>
                    </Box>
                ))}
        </Box>
    );

    const handleChatToggle = () => {
        setChatVisible((prev) => !prev);
    };

    const handleChatInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setChatInput(event.target.value);
    };

    const handleChatSubmit = () => {
        if (chatInput.trim()) {
            setChatMessages((prev) => [...prev, { text: chatInput, sender: 'user' }]);
            setChatInput('');

            setTimeout(() => {
                setChatMessages((prev) => [
                    ...prev,
                    { text: 'You have 5 images that have been created since yesterday.', sender: 'bot' },
                ]);
            }, 1000);
        }
    };

    const renderChatMessages = () => (
        <Box sx={{ flexGrow: 1, overflowY: 'auto', mb: 2 }}>
            {chatMessages.map((message, index) => (
                <Typography key={index} sx={{
                    alignSelf: message.sender === 'user' ? 'flex-end' : 'flex-start',
                    bgcolor: message.sender === 'user' ? '#e0f7fa' : '#f1f1f1',
                    borderRadius: '8px',
                    padding: '8px',
                    margin: '4px 0',
                    maxWidth: '80%',
                    display: 'inline-block'
                }}>
                    {message.text}
                </Typography>
            ))}
        </Box>
    );

    return (
        <>
            <AppBar position="fixed">
                <Toolbar>
                    <Box sx={{ display: 'flex', alignItems: 'center', width: '100%', maxWidth: 1200, mx: 'auto' }}>
                        <Button
                            variant="contained"
                            startIcon={<FilterListIcon />}
                            onClick={handleFilterClick}
                            sx={{ mr: 2 }}
                        >
                            Filter
                        </Button>
                        <TextField
                            label="Search"
                            variant="outlined"
                            size="small"
                            value={searchQuery}
                            onChange={handleSearchChange}
                            sx={{ flexGrow: 1, mr: 2, bgcolor: 'background.paper' }}
                        />
                        <Button
                            variant="contained"
                            startIcon={<SearchIcon />}
                            onClick={handleSearchSubmit}
                        >
                            Search
                        </Button>
                    </Box>
                </Toolbar>
            </AppBar>
            <Popover
                anchorEl={filterAnchorEl}
                open={Boolean(filterAnchorEl)}
                onClose={handleFilterClose}
                anchorOrigin={{
                    vertical: 'bottom',
                    horizontal: 'left',
                }}
                transformOrigin={{
                    vertical: 'top',
                    horizontal: 'left',
                }}
                PaperProps={{
                    style: {
                        maxHeight: '70vh',
                        width: '100%',
                        maxWidth: 600,
                    },
                }}
            >
                <Box sx={{ p: 2 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                        <Typography variant="h6">Filters</Typography>
                        <IconButton onClick={handleFilterClose} size="small">
                            <CloseIcon />
                        </IconButton>
                    </Box>
                    <Box sx={{ mb: 2 }}>
                        <FormControlLabel
                            control={
                                <Switch
                                    checked={filterOptions.creationDate.enabled}
                                    onChange={(event) =>
                                        setFilterOptions((prevState) => ({
                                            ...prevState,
                                            creationDate: { ...prevState.creationDate, enabled: event.target.checked },
                                        }))
                                    }
                                    name="creation-date-toggle"
                                />
                            }
                            label="Creation Date"
                        />
                        {filterOptions.creationDate.enabled && (
                            <Grid container spacing={2} sx={{ mt: 1 }}>
                                <Grid item xs={12} sm={6}>
                                    <LocalizationProvider dateAdapter={AdapterDateFns}>
                                        <DatePicker
                                            label="After"
                                            value={filterOptions.creationDate.after}
                                            onChange={handleDateChange('after')}
                                        />
                                    </LocalizationProvider>
                                </Grid>
                                <Grid item xs={12} sm={6}>
                                    <LocalizationProvider dateAdapter={AdapterDateFns}>
                                        <DatePicker
                                            label="Before"
                                            value={filterOptions.creationDate.before}
                                            onChange={handleDateChange('before')}
                                        />
                                    </LocalizationProvider>
                                </Grid>
                            </Grid>
                        )}
                    </Box>
                    <Grid container spacing={2}>
                        <Grid item xs={12} sm={6}>
                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={filterOptions.media.enabled}
                                        onChange={handleSectionToggle('media')}
                                        name="media-toggle"
                                    />
                                }
                                label="Media"
                            />
                            {filterOptions.media.enabled && renderMediaContent()}
                        </Grid>
                        <Grid item xs={12} sm={6}>
                            <FormControlLabel
                                control={
                                    <Switch
                                        checked={filterOptions.metadata.enabled}
                                        onChange={handleSectionToggle('metadata')}
                                        name="metadata-toggle"
                                    />
                                }
                                label="Metadata"
                            />
                            {filterOptions.metadata.enabled && renderMetadataContent()}
                        </Grid>
                    </Grid>
                    <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 2 }}>
                        <Button variant="contained" onClick={handleSearchSubmit}>
                            Apply Filters
                        </Button>
                    </Box>
                </Box>
            </Popover>
            {chatVisible && (
                <Box
                    sx={{
                        position: 'fixed',
                        right: 0,
                        top: 64,
                        bottom: 0,
                        width: 300,
                        bgcolor: 'background.paper',
                        boxShadow: 3,
                        display: 'flex',
                        flexDirection: 'column',
                        zIndex: 1000,
                        borderRadius: '8px 0 0 8px',
                    }}
                >
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', p: 2, borderBottom: '1px solid rgba(0, 0, 0, 0.12)' }}>
                        <Typography variant="h6">Chat</Typography>
                        <IconButton onClick={handleChatToggle} size="small" sx={{ color: 'text.secondary' }}>
                            <CloseIcon />
                        </IconButton>
                    </Box>
                    <Box sx={{ flexGrow: 1, overflowY: 'auto', p: 2 }}>
                        {renderChatMessages()}
                    </Box>
                    <Box sx={{ p: 2, borderTop: '1px solid rgba(0, 0, 0, 0.12)' }}>
                        <Box sx={{ display: 'flex', alignItems: 'center' }}>
                            <TextField
                                variant="outlined"
                                size="small"
                                value={chatInput}
                                onChange={handleChatInputChange}
                                placeholder="Type your message..."
                                sx={{ flexGrow: 1, mr: 1 }}
                            />
                            <IconButton
                                onClick={handleChatSubmit}
                                sx={{ mr: 1, bgcolor: 'primary.main', color: 'white', '&:hover': { bgcolor: 'primary.dark' } }}
                            >
                                <SendIcon />
                            </IconButton>
                            <IconButton
                                onClick={handleChatToggle}
                                sx={{ bgcolor: 'error.main', color: 'white', '&:hover': { bgcolor: 'error.dark' } }}
                            >
                                <CloseIcon />
                            </IconButton>
                        </Box>
                    </Box>
                </Box>
            )}
        </>
    );
}

export default TopBar;
