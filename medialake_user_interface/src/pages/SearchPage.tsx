import React, { useState } from 'react';
import { Box, Container, TextField, InputAdornment, IconButton, Typography, Paper, Tabs, Tab } from '@mui/material';
import SearchIcon from '@mui/icons-material/Search';
import ClearIcon from '@mui/icons-material/Clear';
import VideoResults from '../components/search/VideoResults';
import ImageResults from '../components/search/ImageResults';
import AudioResults from '../components/search/AudioResults';

// Mock data (replace with actual API calls)
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
    const [searchQuery, setSearchQuery] = useState('');
    const [activeTab, setActiveTab] = useState(0);

    const handleSearch = (event: React.FormEvent) => {
        event.preventDefault();
        // Implement search logic here
        console.log('Searching for:', searchQuery);
    };

    const handleClearSearch = () => {
        setSearchQuery('');
    };

    const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
        setActiveTab(newValue);
    };

    return (
        <Box sx={{
            flexGrow: 1,
            minHeight: '100vh',
            bgcolor: 'grey.50'
        }}>
            <Container maxWidth="xl" sx={{ pt: 4, pb: 8 }}>
                <Typography
                    variant="h4"
                    component="h1"
                    sx={{
                        fontWeight: 600,
                        mb: 4,
                        color: 'primary.main'
                    }}
                >
                    Media Search
                </Typography>

                <Paper
                    component="form"
                    onSubmit={handleSearch}
                    elevation={2}
                    sx={{
                        p: 2,
                        mb: 4,
                        display: 'flex',
                        alignItems: 'center',
                        borderRadius: 2
                    }}
                >
                    <TextField
                        fullWidth
                        variant="outlined"
                        placeholder="Search for videos, images, or audio files..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        InputProps={{
                            startAdornment: (
                                <InputAdornment position="start">
                                    <SearchIcon color="action" />
                                </InputAdornment>
                            ),
                            endAdornment: searchQuery && (
                                <InputAdornment position="end">
                                    <IconButton onClick={handleClearSearch} edge="end">
                                        <ClearIcon />
                                    </IconButton>
                                </InputAdornment>
                            )
                        }}
                        sx={{
                            '& .MuiOutlinedInput-root': {
                                borderRadius: 2
                            }
                        }}
                    />
                </Paper>

                <Paper
                    elevation={2}
                    sx={{
                        borderRadius: 2,
                        overflow: 'hidden'
                    }}
                >
                    <Tabs
                        value={activeTab}
                        onChange={handleTabChange}
                        sx={{
                            borderBottom: 1,
                            borderColor: 'divider',
                            bgcolor: 'background.paper',
                            px: 2
                        }}
                    >
                        <Tab label="All Results" />
                        <Tab label="Videos" />
                        <Tab label="Images" />
                        <Tab label="Audio" />
                    </Tabs>

                    <Box sx={{ p: 3, bgcolor: 'background.paper' }}>
                        {activeTab === 0 && (
                            <>
                                <VideoResults videos={mockVideos} />
                                <ImageResults images={mockImages} />
                                <AudioResults audios={mockAudios} />
                            </>
                        )}
                        {activeTab === 1 && <VideoResults videos={mockVideos} />}
                        {activeTab === 2 && <ImageResults images={mockImages} />}
                        {activeTab === 3 && <AudioResults audios={mockAudios} />}
                    </Box>
                </Paper>
            </Container>
        </Box>
    );
};

export default SearchPage;
