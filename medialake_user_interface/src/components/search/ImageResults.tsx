import React, { useState } from 'react';
import { Box, Grid, Typography, Pagination, IconButton, Menu, MenuItem, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, TableSortLabel, ToggleButtonGroup, ToggleButton } from '@mui/material';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import ViewModuleIcon from '@mui/icons-material/ViewModule';
import ViewListIcon from '@mui/icons-material/ViewList';
import { useNavigate } from 'react-router-dom';

interface ImageItem {
    src: string;
    id: number;
    fileName: string;
    creationDate: string;
    description: string;
}

interface ImageResultsProps {
    images: ImageItem[];
}

type Order = 'asc' | 'desc';
type OrderBy = 'fileName' | 'creationDate';

const ImageResults: React.FC<ImageResultsProps> = ({ images }) => {
    const navigate = useNavigate();
    const [menuAnchorEl, setMenuAnchorEl] = useState<null | HTMLElement>(null);
    const [selectedImage, setSelectedImage] = useState<ImageItem | null>(null);
    const [viewMode, setViewMode] = useState<'card' | 'table'>('card');
    const [order, setOrder] = useState<Order>('asc');
    const [orderBy, setOrderBy] = useState<OrderBy>('fileName');

    const handleImageClick = (imageId: number) => {
        navigate(`/images/${imageId}`);
    };

    const handleMenuOpen = (event: React.MouseEvent<HTMLElement>, image: ImageItem) => {
        event.stopPropagation();
        setMenuAnchorEl(event.currentTarget);
        setSelectedImage(image);
    };

    const handleMenuClose = () => {
        setMenuAnchorEl(null);
        setSelectedImage(null);
    };

    const handleAction = (action: string) => {
        if (!selectedImage) return;

        switch (action) {
            case 'edit':
                console.log('Edit:', selectedImage.fileName);
                break;
            case 'delete':
                console.log('Delete:', selectedImage.fileName);
                break;
            case 'share':
                console.log('Share:', selectedImage.fileName);
                break;
            case 'download':
                console.log('Download:', selectedImage.fileName);
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

    const sortedImages = React.useMemo(() => {
        const comparator = (a: ImageItem, b: ImageItem) => {
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
        return [...images].sort(comparator);
    }, [images, order, orderBy]);

    const renderCardView = () => (
        <Grid container spacing={3}>
            {sortedImages.map((image) => (
                <Grid item xs={12} sm={6} md={4} lg={3} key={image.id}>
                    <Box
                        sx={{
                            position: 'relative',
                            transition: 'all 0.2s ease-in-out',
                            '&:hover': {
                                transform: 'translateY(-4px)'
                            }
                        }}
                    >
                        <Box
                            onClick={() => handleImageClick(image.id)}
                            sx={{
                                cursor: 'pointer',
                                borderRadius: 2,
                                overflow: 'hidden',
                                bgcolor: 'background.paper',
                                boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                                '&:hover': {
                                    boxShadow: '0 8px 16px rgba(0,0,0,0.1)',
                                    '& .image-overlay': {
                                        opacity: 1
                                    }
                                }
                            }}
                        >
                            <Box
                                component="img"
                                height="180"
                                src={image.src}
                                alt={image.fileName}
                                sx={{
                                    width: '100%',
                                    objectFit: 'cover'
                                }}
                            />
                            <Box
                                className="image-overlay"
                                sx={{
                                    position: 'absolute',
                                    top: 0,
                                    left: 0,
                                    right: 0,
                                    bottom: 0,
                                    bgcolor: 'rgba(0, 0, 0, 0.4)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    opacity: 0,
                                    transition: 'opacity 0.2s ease-in-out'
                                }}
                            >
                                <Typography
                                    variant="body1"
                                    sx={{
                                        color: 'white',
                                        textAlign: 'center',
                                        p: 2,
                                        fontWeight: 500
                                    }}
                                >
                                    Click to view details
                                </Typography>
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
                                            {image.fileName}
                                        </Typography>
                                        <Typography
                                            variant="body2"
                                            color="text.secondary"
                                            sx={{ mb: 0.5 }}
                                        >
                                            {new Date(image.creationDate).toLocaleDateString()}
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
                                            onClick={(e) => handleMenuOpen(e, image)}
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
                                    {image.description}
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
                        <TableCell>Preview</TableCell>
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
                    {sortedImages.map((image) => (
                        <TableRow
                            key={image.id}
                            hover
                            onClick={() => handleImageClick(image.id)}
                            sx={{ cursor: 'pointer' }}
                        >
                            <TableCell sx={{ width: 100 }}>
                                <Box
                                    component="img"
                                    src={image.src}
                                    alt={image.fileName}
                                    sx={{
                                        width: 60,
                                        height: 60,
                                        objectFit: 'cover',
                                        borderRadius: 1
                                    }}
                                />
                            </TableCell>
                            <TableCell>{image.fileName}</TableCell>
                            <TableCell>{new Date(image.creationDate).toLocaleDateString()}</TableCell>
                            <TableCell>{image.description}</TableCell>
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
                                        onClick={(e) => handleMenuOpen(e, image)}
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
                        Images
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

            {images.length > 0 && (
                <Box sx={{
                    display: 'flex',
                    justifyContent: 'flex-end',
                    mt: 4
                }}>
                    <Pagination
                        count={Math.ceil(images.length / 12)}
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

export default ImageResults;
