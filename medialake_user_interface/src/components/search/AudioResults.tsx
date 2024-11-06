import React, { useState } from 'react';
import { Box, Grid, Typography, Pagination, IconButton, Menu, MenuItem, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, TableSortLabel, ToggleButtonGroup, ToggleButton } from '@mui/material';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import ViewModuleIcon from '@mui/icons-material/ViewModule';
import ViewListIcon from '@mui/icons-material/ViewList';
import MusicNoteIcon from '@mui/icons-material/MusicNote';

interface AudioItem {
    src: string;
    id: number;
    fileName: string;
    creationDate: string;
    description: string;
}

interface AudioResultsProps {
    audios: AudioItem[];
}

type Order = 'asc' | 'desc';
type OrderBy = 'fileName' | 'creationDate';

const AudioResults: React.FC<AudioResultsProps> = ({ audios }) => {
    const [menuAnchorEl, setMenuAnchorEl] = useState<null | HTMLElement>(null);
    const [selectedAudio, setSelectedAudio] = useState<AudioItem | null>(null);
    const [viewMode, setViewMode] = useState<'card' | 'table'>('card');
    const [order, setOrder] = useState<Order>('asc');
    const [orderBy, setOrderBy] = useState<OrderBy>('fileName');

    const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, audio: AudioItem) => {
        event.stopPropagation();
        setMenuAnchorEl(event.currentTarget);
        setSelectedAudio(audio);
    };

    const handleMenuClose = () => {
        setMenuAnchorEl(null);
        setSelectedAudio(null);
    };

    const handleAction = (action: string) => {
        if (!selectedAudio) return;

        switch (action) {
            case 'edit':
                console.log('Edit:', selectedAudio.fileName);
                break;
            case 'delete':
                console.log('Delete:', selectedAudio.fileName);
                break;
            case 'share':
                console.log('Share:', selectedAudio.fileName);
                break;
            case 'download':
                console.log('Download:', selectedAudio.fileName);
                break;
        }
        handleMenuClose();
    };

    const handleViewModeChange = (event: React.MouseEvent<HTMLElement>, newMode: 'card' | 'table' | null) => {
        if (newMode !== null) {
            setViewMode(newMode);
        }
    };

    const handleRequestSort = (property: OrderBy) => {
        const isAsc = orderBy === property && order === 'asc';
        setOrder(isAsc ? 'desc' : 'asc');
        setOrderBy(property);
    };

    const sortedAudios = React.useMemo(() => {
        const comparator = (a: AudioItem, b: AudioItem) => {
            if (orderBy === 'fileName') {
                return order === 'asc'
                    ? a.fileName.localeCompare(b.fileName)
                    : b.fileName.localeCompare(a.fileName);
            } else {
                return order === 'asc'
                    ? new Date(a.creationDate).getTime() - new Date(b.creationDate).getTime()
                    : new Date(b.creationDate).getTime() - new Date(a.creationDate).getTime();
            }
        };
        return [...audios].sort(comparator);
    }, [audios, order, orderBy]);

    const renderCardView = () => (
        <Grid container spacing={3}>
            {sortedAudios.map((audio) => (
                <Grid item xs={12} sm={6} md={4} lg={3} key={audio.id}>
                    <Box
                        sx={{
                            position: 'relative',
                            transition: 'all 0.2s ease-in-out',
                            '&:hover': {
                                transform: 'translateY(-4px)'
                            }
                        }}
                    >
                        <Box sx={{
                            borderRadius: 2,
                            overflow: 'hidden',
                            bgcolor: 'background.paper',
                            boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                            '&:hover': {
                                boxShadow: '0 8px 16px rgba(0,0,0,0.1)'
                            }
                        }}>
                            <Box sx={{
                                height: 120,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                background: 'linear-gradient(45deg, #2196F3 30%, #21CBF3 90%)',
                                position: 'relative'
                            }}>
                                <MusicNoteIcon sx={{ fontSize: 48, color: 'white' }} />
                                <Box
                                    component="audio"
                                    src={audio.src}
                                    title={audio.fileName}
                                    controls
                                    sx={{
                                        position: 'absolute',
                                        bottom: 0,
                                        width: '100%',
                                        bgcolor: 'rgba(0, 0, 0, 0.5)',
                                        '& audio': {
                                            width: '100%'
                                        }
                                    }}
                                />
                            </Box>
                            <Box sx={{ p: 2 }}>
                                <Box sx={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'flex-start',
                                }}>
                                    <Box sx={{ flex: 1, mr: 1 }}>
                                        <Typography
                                            variant="subtitle1"
                                            sx={{
                                                fontWeight: 500,
                                                overflow: 'hidden',
                                                textOverflow: 'ellipsis',
                                                display: '-webkit-box',
                                                WebkitLineClamp: 2,
                                                WebkitBoxOrient: 'vertical',
                                                lineHeight: 1.2,
                                                mb: 0.5
                                            }}
                                        >
                                            {audio.fileName}
                                        </Typography>
                                        <Typography
                                            variant="body2"
                                            color="text.secondary"
                                            sx={{ mb: 0.5 }}
                                        >
                                            {new Date(audio.creationDate).toLocaleDateString()}
                                        </Typography>
                                    </Box>
                                    <Box sx={{
                                        display: 'flex',
                                        gap: 0.5,
                                        opacity: 0.7,
                                        '&:hover': {
                                            opacity: 1
                                        }
                                    }}>
                                        <IconButton
                                            size="small"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleAction('edit');
                                            }}
                                            sx={{
                                                bgcolor: 'background.paper',
                                                '&:hover': {
                                                    bgcolor: 'action.hover'
                                                }
                                            }}
                                        >
                                            <EditIcon fontSize="small" />
                                        </IconButton>
                                        <IconButton
                                            size="small"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleAction('delete');
                                            }}
                                            sx={{
                                                bgcolor: 'background.paper',
                                                '&:hover': {
                                                    bgcolor: 'action.hover'
                                                }
                                            }}
                                        >
                                            <DeleteIcon fontSize="small" />
                                        </IconButton>
                                        <IconButton
                                            size="small"
                                            onClick={(e) => handleMenuOpen(e, audio)}
                                            sx={{
                                                bgcolor: 'background.paper',
                                                '&:hover': {
                                                    bgcolor: 'action.hover'
                                                }
                                            }}
                                        >
                                            <MoreVertIcon fontSize="small" />
                                        </IconButton>
                                    </Box>
                                </Box>
                                <Typography
                                    variant="body2"
                                    color="text.secondary"
                                    sx={{
                                        overflow: 'hidden',
                                        textOverflow: 'ellipsis',
                                        display: '-webkit-box',
                                        WebkitLineClamp: 2,
                                        WebkitBoxOrient: 'vertical',
                                        mt: 1,
                                        lineHeight: 1.3
                                    }}
                                >
                                    {audio.description}
                                </Typography>
                            </Box>
                        </Box>
                    </Box>
                </Grid>
            ))}
        </Grid>
    );

    const renderTableView = () => (
        <TableContainer component={Paper} sx={{ mt: 2, borderRadius: 2 }}>
            <Table>
                <TableHead>
                    <TableRow>
                        <TableCell>Audio</TableCell>
                        <TableCell>
                            <TableSortLabel
                                active={orderBy === 'fileName'}
                                direction={orderBy === 'fileName' ? order : 'asc'}
                                onClick={() => handleRequestSort('fileName')}
                            >
                                Name
                            </TableSortLabel>
                        </TableCell>
                        <TableCell>
                            <TableSortLabel
                                active={orderBy === 'creationDate'}
                                direction={orderBy === 'creationDate' ? order : 'asc'}
                                onClick={() => handleRequestSort('creationDate')}
                            >
                                Created
                            </TableSortLabel>
                        </TableCell>
                        <TableCell>Description</TableCell>
                        <TableCell align="right">Actions</TableCell>
                    </TableRow>
                </TableHead>
                <TableBody>
                    {sortedAudios.map((audio) => (
                        <TableRow
                            key={audio.id}
                            hover
                            sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
                        >
                            <TableCell sx={{ width: 250 }}>
                                <Box
                                    component="audio"
                                    src={audio.src}
                                    title={audio.fileName}
                                    controls
                                    sx={{
                                        width: '100%',
                                        '& audio': {
                                            width: '100%'
                                        }
                                    }}
                                />
                            </TableCell>
                            <TableCell>{audio.fileName}</TableCell>
                            <TableCell>{new Date(audio.creationDate).toLocaleDateString()}</TableCell>
                            <TableCell>{audio.description}</TableCell>
                            <TableCell align="right">
                                <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
                                    <IconButton
                                        size="small"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleAction('edit');
                                        }}
                                    >
                                        <EditIcon fontSize="small" />
                                    </IconButton>
                                    <IconButton
                                        size="small"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            handleAction('delete');
                                        }}
                                    >
                                        <DeleteIcon fontSize="small" />
                                    </IconButton>
                                    <IconButton
                                        size="small"
                                        onClick={(e) => handleMenuOpen(e, audio)}
                                    >
                                        <MoreVertIcon fontSize="small" />
                                    </IconButton>
                                </Box>
                            </TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </TableContainer>
    );

    return (
        <Box>
            <Box sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                mb: 3
            }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <Typography
                        variant="h5"
                        component="h2"
                        sx={{
                            fontWeight: 600,
                            color: 'text.primary',
                        }}
                    >
                        Audio
                    </Typography>
                    <ToggleButtonGroup
                        value={viewMode}
                        exclusive
                        onChange={handleViewModeChange}
                        size="small"
                    >
                        <ToggleButton value="card">
                            <ViewModuleIcon />
                        </ToggleButton>
                        <ToggleButton value="table">
                            <ViewListIcon />
                        </ToggleButton>
                    </ToggleButtonGroup>
                </Box>
            </Box>

            {viewMode === 'card' ? renderCardView() : renderTableView()}

            {audios.length > 0 && (
                <Box sx={{
                    display: 'flex',
                    justifyContent: 'flex-end',
                    mt: 4
                }}>
                    <Pagination
                        count={Math.ceil(audios.length / 12)}
                        color="primary"
                        size="medium"
                        shape="rounded"
                        sx={{
                            '& .MuiPaginationItem-root': {
                                borderRadius: 1
                            }
                        }}
                    />
                </Box>
            )}

            <Menu
                anchorEl={menuAnchorEl}
                open={Boolean(menuAnchorEl)}
                onClose={handleMenuClose}
                onClick={(e) => e.stopPropagation()}
                PaperProps={{
                    elevation: 3,
                    sx: {
                        minWidth: 150,
                        borderRadius: 2,
                        mt: 1
                    }
                }}
            >
                <MenuItem onClick={() => handleAction('share')}>Share</MenuItem>
                <MenuItem onClick={() => handleAction('download')}>Download</MenuItem>
            </Menu>
        </Box>
    );
};

export default AudioResults;
