import React, { useState } from 'react';
import { Box, Grid, Typography, Pagination, IconButton, Menu, MenuItem, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, TableSortLabel, ToggleButtonGroup, ToggleButton, TextField } from '@mui/material';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import ViewModuleIcon from '@mui/icons-material/ViewModule';
import ViewListIcon from '@mui/icons-material/ViewList';
import { useNavigate } from 'react-router-dom';
import { ConfirmationModal } from '../common/ConfirmationModal';

export interface ImageItem {
    inventoryId: string;
    assetId: string;
    assetType: string;
    createDate: string;
    mainRepresentation: {
        id: string;
        type: string;
        format: string;
        purpose: string;
        storage: {
            storageType: string;
            bucket: string;
            path: string;
            status: string;
            fileSize: number;
            hashValue: string;
        };
        imageSpec?: {
            colorSpace: string | null;
            width: number | null;
            height: number | null;
            dpi: number | null;
        };
    };
    derivedRepresentations: Array<{
        id: string;
        type: string;
        format: string;
        purpose: string;
        storage: {
            storageType: string;
            bucket: string;
            path: string;
            status: string;
            fileSize: number;
            hashValue: string | null;
        };
        imageSpec?: {
            colorSpace: string | null;
            width: number | null;
            height: number | null;
            dpi: number | null;
        };
    }>;
    metadata: any;
    score: number;
    thumbnailUrl: string | null;
}

interface ImageResultsProps {
    images: ImageItem[];
}

type Order = 'asc' | 'desc';
type OrderBy = 'path' | 'createDate';

const ITEMS_PER_PAGE = 12;

const ImageResults: React.FC<ImageResultsProps> = ({ images }) => {
    // Rest of the component implementation remains the same
    const navigate = useNavigate();
    const [menuAnchorEl, setMenuAnchorEl] = useState<null | HTMLElement>(null);
    const [selectedImage, setSelectedImage] = useState<ImageItem | null>(null);
    const [viewMode, setViewMode] = useState<'card' | 'table'>('card');
    const [order, setOrder] = useState<Order>('asc');
    const [orderBy, setOrderBy] = useState<OrderBy>('path');
    const [page, setPage] = useState(1);
    const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
    const [imageToDelete, setImageToDelete] = useState<ImageItem | null>(null);
    const [editingImageId, setEditingImageId] = useState<string | null>(null);
    const [editedName, setEditedName] = useState<string>('');
    const [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
    const [imageToRename, setImageToRename] = useState<{
        image: ImageItem;
        newName: string;
    } | null>(null);

    const getImageUrl = (image: ImageItem) => {
        return image.thumbnailUrl || 'https://via.placeholder.com/400x300';
    };

    const handleImageClick = (imageId: string) => {
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
                console.log('Edit:', selectedImage.mainRepresentation.storage.path);
                break;
            case 'delete':
                console.log('Delete:', selectedImage.mainRepresentation.storage.path);
                break;
            case 'share':
                console.log('Share:', selectedImage.mainRepresentation.storage.path);
                break;
            case 'download':
                window.open(getImageUrl(selectedImage), '_blank');
                break;
        }
        handleMenuClose();
    };

    const handleViewModeChange = (event: React.MouseEvent<HTMLElement>, newMode: 'card' | 'table' | null) => {
        if (newMode !== null) {
            setViewMode(newMode);
            setPage(1); // Reset to first page when changing view mode
        }
    };

    const handleRequestSort = (property: OrderBy) => {
        const isAsc = orderBy === property && order === 'asc';
        setOrder(isAsc ? 'desc' : 'asc');
        setOrderBy(property);
        setPage(1); // Reset to first page when sorting
    };

    const handlePageChange = (event: React.ChangeEvent<unknown>, value: number) => {
        setPage(value);
    };

    const sortedImages = React.useMemo(() => {
        const comparator = (a: ImageItem, b: ImageItem) => {
            if (orderBy === 'path') {
                return order === 'asc'
                    ? a.mainRepresentation.storage.path.localeCompare(b.mainRepresentation.storage.path)
                    : b.mainRepresentation.storage.path.localeCompare(a.mainRepresentation.storage.path);
            } else {
                return order === 'asc'
                    ? new Date(a.createDate).getTime() - new Date(b.createDate).getTime()
                    : new Date(b.createDate).getTime() - new Date(a.createDate).getTime();
            }
        };
        return [...images].sort(comparator);
    }, [images, order, orderBy]);

    // Calculate pagination
    const totalPages = Math.ceil(sortedImages.length / ITEMS_PER_PAGE);
    const startIndex = (page - 1) * ITEMS_PER_PAGE;
    const paginatedImages = sortedImages.slice(startIndex, startIndex + ITEMS_PER_PAGE);

    const handleDeleteClick = (event: React.MouseEvent<HTMLElement>, image: ImageItem) => {
        event.stopPropagation();
        setImageToDelete(image);
        setIsDeleteModalOpen(true);
    };

    const handleDeleteConfirm = async () => {
        // TODO: Implement actual delete logic
        console.log('Deleting image:', imageToDelete?.inventoryId);
        setIsDeleteModalOpen(false);
        setImageToDelete(null);
    };

    const handleStartEditing = (image: ImageItem) => {
        setEditingImageId(image.inventoryId);
        setEditedName(image.mainRepresentation.storage.path);
    };

    const handleNameChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setEditedName(event.target.value);
    };

    const handleNameEditComplete = (image: ImageItem) => {
        if (editedName !== image.mainRepresentation.storage.path) {
            setImageToRename({ image, newName: editedName });
            setIsRenameModalOpen(true);
        }
        setEditingImageId(null);
    };

    const handleRenameConfirm = async () => {
        if (imageToRename) {
            // TODO: Implement actual rename logic
            console.log('Renaming image:', imageToRename.image.inventoryId, 'to:', imageToRename.newName);
        }
        setIsRenameModalOpen(false);
        setImageToRename(null);
        setEditedName('');
    };

    const handleRenameCancel = () => {
        setIsRenameModalOpen(false);
        setImageToRename(null);
        setEditedName('');
    };

    const renderCardView = () => (
        <Grid container spacing={3}>
            {paginatedImages.map((image) => (
                <Grid item xs={12} sm={6} md={4} lg={3} key={image.inventoryId}>
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
                            onClick={() => handleImageClick(image.inventoryId)}
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
                                src={getImageUrl(image)}
                                alt={image.mainRepresentation.storage.path}
                                sx={{
                                    width: '100%',
                                    height: 300,
                                    objectFit: 'cover',
                                    backgroundColor: 'rgba(0,0,0,0.03)'
                                }}
                            />
                            <Box sx={{ p: 2 }}>
                                <Box sx={{ mb: 2 }}>
                                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                                        <Box sx={{ wordBreak: 'break-word' }}>
                                            <Typography
                                                variant="body2"
                                                color="text.secondary"
                                                sx={{ mb: 0.5 }}
                                            >
                                                Name:
                                            </Typography>
                                            <Typography
                                                variant="subtitle1"
                                                sx={{
                                                    fontWeight: 500,
                                                    wordBreak: 'break-word',
                                                    lineHeight: 1.2,
                                                }}
                                            >
                                                {image.mainRepresentation.storage.path}
                                            </Typography>
                                        </Box>
                                        <Typography
                                            variant="body2"
                                            color="text.secondary"
                                        >
                                            Format: {image.mainRepresentation.format}
                                        </Typography>
                                        <Box sx={{
                                            display: 'flex',
                                            justifyContent: 'space-between',
                                            alignItems: 'center'
                                        }}>
                                            <Typography
                                                variant="body2"
                                                color="text.secondary"
                                            >
                                                Created: {new Date(image.createDate).toLocaleDateString()}
                                            </Typography>
                                            <Box sx={{
                                                display: 'flex',
                                                gap: 1
                                            }}>
                                                <IconButton
                                                    size="small"
                                                    onClick={(e) => handleDeleteClick(e, image)}
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
                                        </Box>
                                    </Box>
                                </Box>
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
                                active={orderBy === 'path'}
                                direction={orderBy === 'path' ? order : 'asc'}
                                onClick={() => handleRequestSort('path')}
                            >
                                Name
                            </TableSortLabel>
                        </TableCell>
                        <TableCell>Format</TableCell>
                        <TableCell>
                            <TableSortLabel
                                active={orderBy === 'createDate'}
                                direction={orderBy === 'createDate' ? order : 'asc'}
                                onClick={() => handleRequestSort('createDate')}
                            >
                                Created
                            </TableSortLabel>
                        </TableCell>
                        <TableCell /> {/* Empty header cell for actions */}
                    </TableRow>
                </TableHead>
                <TableBody>
                    {paginatedImages.map((image) => (
                        <TableRow
                            key={image.inventoryId}
                            hover
                            onClick={() => handleImageClick(image.inventoryId)}
                            sx={{ cursor: 'pointer' }}
                        >
                            <TableCell sx={{ width: 100 }}>
                                <Box
                                    component="img"
                                    src={getImageUrl(image)}
                                    alt={image.mainRepresentation.storage.path}
                                    sx={{
                                        width: 60,
                                        height: 60,
                                        objectFit: 'cover',
                                        borderRadius: 1
                                    }}
                                />
                            </TableCell>
                            <TableCell>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                    {editingImageId === image.inventoryId ? (
                                        <TextField
                                            value={editedName}
                                            onChange={handleNameChange}
                                            onBlur={() => handleNameEditComplete(image)}
                                            onKeyPress={(e) => {
                                                if (e.key === 'Enter') {
                                                    handleNameEditComplete(image);
                                                }
                                            }}
                                            onClick={(e) => e.stopPropagation()}
                                            autoFocus
                                            fullWidth
                                            size="small"
                                        />
                                    ) : (
                                        <>
                                            <Typography>{image.mainRepresentation.storage.path}</Typography>
                                            <IconButton
                                                size="small"
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    handleStartEditing(image);
                                                }}
                                            >
                                                <EditIcon fontSize="small" />
                                            </IconButton>
                                        </>
                                    )}
                                </Box>
                            </TableCell>
                            <TableCell>{image.mainRepresentation.format}</TableCell>
                            <TableCell>
                                <Box sx={{
                                    display: 'flex',
                                    justifyContent: 'space-between',
                                    alignItems: 'center'
                                }}>
                                    {new Date(image.createDate).toLocaleDateString()}
                                    <Box sx={{ display: 'flex', gap: 1 }}>
                                        <IconButton
                                            size="small"
                                            onClick={(e) => handleDeleteClick(e, image)}
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

            {images.length > ITEMS_PER_PAGE && (
                <Box sx={{
                    display: 'flex',
                    justifyContent: 'flex-end',
                    mt: 4,
                    mb: 2
                }}>
                    <Pagination
                        count={totalPages}
                        page={page}
                        onChange={handlePageChange}
                        color="primary"
                        size="medium"
                        shape="circular"
                        sx={{
                            '& .MuiPaginationItem-root': {
                                borderRadius: '50%',
                                minWidth: 40,
                                height: 40,
                                '&.Mui-selected': {
                                    fontWeight: 'bold',
                                    backgroundColor: 'primary.main',
                                    color: 'white',
                                    '&:hover': {
                                        backgroundColor: 'primary.dark',
                                    }
                                }
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
                <MenuItem onClick={() => {
                    handleMenuClose();
                    if (selectedImage) {
                        handleStartEditing(selectedImage);
                    }
                }}>
                    Rename
                </MenuItem>
                <MenuItem onClick={() => handleAction('share')}>Share</MenuItem>
                <MenuItem onClick={() => handleAction('download')}>Download</MenuItem>
            </Menu>

            <ConfirmationModal
                open={isDeleteModalOpen}
                title="Delete Image"
                message={`Are you sure you want to delete "${imageToDelete?.mainRepresentation.storage.path}"? This action cannot be undone.`}
                onConfirm={handleDeleteConfirm}
                onCancel={() => {
                    setIsDeleteModalOpen(false);
                    setImageToDelete(null);
                }}
                confirmText="Delete Image"
            />

            <ConfirmationModal
                open={isRenameModalOpen}
                title="Rename Image"
                message={`Are you sure you want to rename "${imageToRename?.image.mainRepresentation.storage.path}" to "${imageToRename?.newName}"?`}
                onConfirm={handleRenameConfirm}
                onCancel={handleRenameCancel}
                confirmText="Rename"
                cancelText="Cancel"
            />
        </Box>
    );
};

export default ImageResults;
