import React, { useState } from 'react';
import { Box, Grid, Typography, Pagination, IconButton, Menu, MenuItem, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, TableSortLabel, ToggleButtonGroup, ToggleButton, TextField } from '@mui/material';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import DeleteIcon from '@mui/icons-material/Delete';
import EditIcon from '@mui/icons-material/Edit';
import ViewModuleIcon from '@mui/icons-material/ViewModule';
import ViewListIcon from '@mui/icons-material/ViewList';
import { useNavigate } from 'react-router-dom';
import { ConfirmationModal } from '../common/ConfirmationModal';
import { useRenameAsset, useDeleteAsset } from '../../api/hooks/useAssets';
import { RenameDialog } from '../common/RenameDialog';
import ViewColumnIcon from '@mui/icons-material/ViewColumn';
import Popover from '@mui/material/Popover';
import FormGroup from '@mui/material/FormGroup';
import FormControlLabel from '@mui/material/FormControlLabel';
import Checkbox from '@mui/material/Checkbox';
import SortIcon from '@mui/icons-material/Sort';
import SettingsIcon from '@mui/icons-material/Settings';
import { ImageItem, ImageResultsProps, ImageToRename, CardFieldConfig, ColumnConfig, Order, OrderBy  } from '@/types/search/searchResults'

const ITEMS_PER_PAGE = 12;

// Move formatFileSize outside of the component to make it available everywhere
const formatFileSize = (bytes: number): string => {
    if (!bytes) return '-';
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex++;
    }
    return `${size.toFixed(1)} ${units[unitIndex]}`;
};

// Move renderCardField before the component as well
const renderCardField = (fieldId: string, image: ImageItem): string => {
    switch (fieldId) {
        case 'name':
            return image.mainRepresentation.storage.path;
        case 'format':
            return image.mainRepresentation.format;
        case 'createDate':
            return new Date(image.createDate).toLocaleDateString();
        case 'fileSize':
            return formatFileSize(image.mainRepresentation.storage.fileSize);
        case 'dimensions':
            const spec = image.mainRepresentation.imageSpec;
            return spec?.width && spec?.height ? `${spec.width}x${spec.height}` : '-';
        default:
            return '';
    }
};

const ImageResults: React.FC<ImageResultsProps> = ({ images }) => {
    // Deduplicate results based on inventoryId
    const uniqueResults = images.reduce((acc, current) => {
        // Take the most complete version of each asset (one with thumbnail)
        const existing = acc.get(current.inventoryId);
        if (!existing || (!existing.thumbnailUrl && current.thumbnailUrl)) {
            acc.set(current.inventoryId, current);
        }
        return acc;
    }, new Map());

    const deduplicatedResults = Array.from(uniqueResults.values());

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
    const [imageToRename, setImageToRename] = useState<ImageToRename | null>(null);
    const [isRenameDialogOpen, setIsRenameDialogOpen] = useState(false);
    const renameAsset = useRenameAsset();
    const deleteAsset = useDeleteAsset();

    const [columns, setColumns] = useState<ColumnConfig[]>([
        {
            id: 'preview',
            label: 'Preview',
            visible: true,
            minWidth: 100
        },
        {
            id: 'path',
            label: 'Name',
            visible: true,
            minWidth: 200,
        },
        {
            id: 'format',
            label: 'Format',
            visible: true,
            minWidth: 100,
        },
        {
            id: 'createDate',
            label: 'Created',
            visible: true,
            minWidth: 120,
            format: (value: string) => new Date(value).toLocaleDateString(),
        },
        {
            id: 'fileSize',
            label: 'Size',
            visible: false,
            minWidth: 100,
            format: (value: number) => formatFileSize(value),
        },
        {
            id: 'dimensions',
            label: 'Dimensions',
            visible: false,
            minWidth: 120,
            format: (image: ImageItem) => {
                const spec = image.mainRepresentation.imageSpec;
                return spec?.width && spec?.height ? `${spec.width}x${spec.height}` : '-';
            },
        },
        {
            id: 'actions',
            label: 'Actions',
            visible: true,
            minWidth: 100,
            align: 'right',
        },
    ]);

    const [columnSelectorAnchor, setColumnSelectorAnchor] = useState<null | HTMLElement>(null);

    const [cardSortAnchor, setCardSortAnchor] = useState<null | HTMLElement>(null);
    const [cardFieldsAnchor, setCardFieldsAnchor] = useState<null | HTMLElement>(null);
    const [cardSortBy, setCardSortBy] = useState<OrderBy>('createDate');
    const [cardSortOrder, setCardSortOrder] = useState<Order>('desc');
    const [cardFields, setCardFields] = useState<CardFieldConfig[]>([
        { id: 'name', label: 'Name', visible: true },
        { id: 'format', label: 'Format', visible: true },
        { id: 'createDate', label: 'Created Date', visible: true },
        { id: 'fileSize', label: 'File Size', visible: false },
        { id: 'dimensions', label: 'Dimensions', visible: false },
    ]);

    const handleColumnToggle = (columnId: string) => {
        setColumns(columns.map(col =>
            col.id === columnId ? { ...col, visible: !col.visible } : col
        ));
    };

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
            switch (orderBy) {
                case 'path':
                    return order === 'asc'
                        ? a.mainRepresentation.storage.path.localeCompare(b.mainRepresentation.storage.path)
                        : b.mainRepresentation.storage.path.localeCompare(a.mainRepresentation.storage.path);
                case 'format':
                    return order === 'asc'
                        ? a.mainRepresentation.format.localeCompare(b.mainRepresentation.format)
                        : b.mainRepresentation.format.localeCompare(a.mainRepresentation.format);
                case 'createDate':
                    return order === 'asc'
                        ? new Date(a.createDate).getTime() - new Date(b.createDate).getTime()
                        : new Date(b.createDate).getTime() - new Date(a.createDate).getTime();
                case 'fileSize':
                    const aSize = a.mainRepresentation.storage.fileSize || 0;
                    const bSize = b.mainRepresentation.storage.fileSize || 0;
                    return order === 'asc' ? aSize - bSize : bSize - aSize;
                case 'dimensions':
                    const aWidth = a.mainRepresentation.imageSpec?.width || 0;
                    const bWidth = b.mainRepresentation.imageSpec?.width || 0;
                    const aHeight = a.mainRepresentation.imageSpec?.height || 0;
                    const bHeight = b.mainRepresentation.imageSpec?.height || 0;
                    const aPixels = aWidth * aHeight;
                    const bPixels = bWidth * bHeight;
                    return order === 'asc' ? aPixels - bPixels : bPixels - aPixels;
                default:
                    return 0;
            }
        };
        return [...deduplicatedResults].sort(comparator);
    }, [deduplicatedResults, order, orderBy]);

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
        if (imageToDelete) {
            try {
                await deleteAsset.mutateAsync(imageToDelete.inventoryId);
                setIsDeleteModalOpen(false);
                setImageToDelete(null);
            } catch (error) {
                // Error handling is done in the mutation
                setIsDeleteModalOpen(false);
                setImageToDelete(null);
            }
        }
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
            setIsRenameDialogOpen(true);
        }
        setEditingImageId(null);
    };

    const handleRenameConfirm = async (newName: string) => {
        const imageToRename = selectedImage;
        if (imageToRename) {
            try {
                await renameAsset.mutateAsync({
                    inventoryId: imageToRename.inventoryId,
                    newName
                });
                setIsRenameDialogOpen(false);
                setSelectedImage(null);
                setEditedName('');
            } catch (error) {
                // Error handling is done in the mutation
            }
        }
    };

    const handleRenameCancel = () => {
        setIsRenameDialogOpen(false);
        setImageToRename(null);
        setEditedName('');
    };

    const handleRenameClick = (image: ImageItem) => {
        setSelectedImage(image);
        setIsRenameDialogOpen(true);
    };

    const handleCardSortChange = (field: OrderBy) => {
        if (cardSortBy === field) {
            setCardSortOrder(cardSortOrder === 'asc' ? 'desc' : 'asc');
        } else {
            setCardSortBy(field);
            setCardSortOrder('asc');
        }
        setOrder(cardSortOrder);
        setOrderBy(field);
    };

    const handleCardFieldToggle = (fieldId: string) => {
        setCardFields(cardFields.map(field =>
            field.id === fieldId ? { ...field, visible: !field.visible } : field
        ));
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
                        {columns.filter(col => col.visible).map((column) => (
                            <TableCell
                                key={column.id}
                                align={column.align}
                                style={{ minWidth: column.minWidth }}
                            >
                                {column.id !== 'preview' && column.id !== 'actions' ? (
                                    <TableSortLabel
                                        active={orderBy === column.id}
                                        direction={orderBy === column.id ? order : 'asc'}
                                        onClick={() => handleRequestSort(column.id as OrderBy)}
                                    >
                                        {column.label}
                                    </TableSortLabel>
                                ) : (
                                    column.label
                                )}
                            </TableCell>
                        ))}
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
                            {columns.filter(col => col.visible).map((column) => (
                                <TableCell key={column.id} align={column.align}>
                                    {renderTableCell(column, image)}
                                </TableCell>
                            ))}
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </TableContainer>
    );

    const renderTableCell = (column: ColumnConfig, image: ImageItem) => {
        switch (column.id) {
            case 'preview':
                return (
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
                );
            case 'path':
                return (
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        {editingImageId === image.inventoryId ? (
                            <TextField
                                value={editedName}
                                onChange={handleNameChange}
                                onBlur={() => handleTableNameEditComplete(image)}
                                onKeyPress={(e) => {
                                    if (e.key === 'Enter') {
                                        handleTableNameEditComplete(image);
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
                );
            case 'format':
                return image.mainRepresentation.format;
            case 'createDate':
                return column.format ? column.format(image.createDate) : image.createDate;
            case 'fileSize':
                return column.format ? column.format(image.mainRepresentation.storage.fileSize) : '-';
            case 'dimensions':
                return column.format ? column.format(image) : '-';
            case 'actions':
                return (
                    <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
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
                );
            default:
                return null;
        }
    };

    const handleTableNameEditComplete = async (image: ImageItem) => {
        if (editedName !== image.mainRepresentation.storage.path) {
            try {
                await renameAsset.mutateAsync({
                    inventoryId: image.inventoryId,
                    newName: editedName
                });
            } catch (error) {
                // Error handling is done in the mutation
            }
        }
        setEditingImageId(null);
        setEditedName('');
    };

    const handleCardRenameClick = (image: ImageItem) => {
        setSelectedImage(image);
        setIsRenameDialogOpen(true);
    };

    const renderMenu = () => (
        <Menu
            anchorEl={menuAnchorEl}
            open={Boolean(menuAnchorEl)}
            onClose={handleMenuClose}
            onClick={(e) => e.stopPropagation()}
        >
            {viewMode === 'card' && (
                <MenuItem onClick={() => {
                    handleMenuClose();
                    if (selectedImage) {
                        handleCardRenameClick(selectedImage);
                    }
                }}>
                    Rename
                </MenuItem>
            )}
            <MenuItem onClick={() => handleAction('share')}>Share</MenuItem>
            <MenuItem onClick={() => handleAction('download')}>Download</MenuItem>
        </Menu>
    );

    const renderViewControls = () => (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
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
            {viewMode === 'table' && (
                <IconButton
                    onClick={(e) => setColumnSelectorAnchor(e.currentTarget)}
                    size="small"
                    sx={{ ml: 1 }}
                >
                    <ViewColumnIcon />
                </IconButton>
            )}
        </Box>
    );

    const CardSortMenu = () => (
        <Popover
            open={Boolean(cardSortAnchor)}
            anchorEl={cardSortAnchor}
            onClose={() => setCardSortAnchor(null)}
            anchorOrigin={{
                vertical: 'bottom',
                horizontal: 'right',
            }}
            transformOrigin={{
                vertical: 'top',
                horizontal: 'right',
            }}
        >
            <Box sx={{ p: 2, minWidth: 200 }}>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                    Sort By
                </Typography>
                {[
                    { id: 'createDate', label: 'Created Date' },
                    { id: 'path', label: 'Name' },
                    { id: 'format', label: 'Format' },
                    { id: 'fileSize', label: 'File Size' },
                    { id: 'dimensions', label: 'Dimensions' },
                ].map((option) => (
                    <MenuItem
                        key={option.id}
                        onClick={() => {
                            handleCardSortChange(option.id as OrderBy);
                            setCardSortAnchor(null);
                        }}
                        sx={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            py: 1,
                        }}
                    >
                        <Typography variant="body2">
                            {option.label}
                        </Typography>
                        {cardSortBy === option.id && (
                            <Typography variant="caption" color="primary">
                                {cardSortOrder === 'asc' ? '↑' : '↓'}
                            </Typography>
                        )}
                    </MenuItem>
                ))}
            </Box>
        </Popover>
    );

    const CardFieldsMenu = () => (
        <Popover
            open={Boolean(cardFieldsAnchor)}
            anchorEl={cardFieldsAnchor}
            onClose={() => setCardFieldsAnchor(null)}
            anchorOrigin={{
                vertical: 'bottom',
                horizontal: 'right',
            }}
            transformOrigin={{
                vertical: 'top',
                horizontal: 'right',
            }}
            onClick={(e) => e.stopPropagation()}
            slotProps={{
                paper: {
                    onClick: (e) => e.stopPropagation(),
                    sx: { p: 2, minWidth: 200 }
                },
            }}
        >
            <Box>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                    Show Fields
                </Typography>
                <FormGroup onClick={(e) => e.stopPropagation()}>
                    {cardFields.map((field) => (
                        <FormControlLabel
                            key={field.id}
                            control={
                                <Checkbox
                                    checked={field.visible}
                                    onChange={(e) => {
                                        e.stopPropagation();
                                        handleCardFieldToggle(field.id);
                                    }}
                                    size="small"
                                    onClick={(e) => e.stopPropagation()}
                                />
                            }
                            label={field.label}
                            onClick={(e) => e.stopPropagation()}
                            sx={{
                                '& .MuiFormControlLabel-label': {
                                    fontSize: '0.875rem'
                                }
                            }}
                        />
                    ))}
                </FormGroup>
            </Box>
        </Popover>
    );

    const ColumnSelector = () => (
        <Popover
            open={Boolean(columnSelectorAnchor)}
            anchorEl={columnSelectorAnchor}
            onClose={() => setColumnSelectorAnchor(null)}
            anchorOrigin={{
                vertical: 'bottom',
                horizontal: 'right',
            }}
            transformOrigin={{
                vertical: 'top',
                horizontal: 'right',
            }}
            onClick={(e) => e.stopPropagation()}
            slotProps={{
                paper: {
                    onClick: (e) => e.stopPropagation(),
                    sx: { p: 2, minWidth: 200 }
                },
            }}
        >
            <Box>
                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                    Show Columns
                </Typography>
                <FormGroup onClick={(e) => e.stopPropagation()}>
                    {columns.map((column) => (
                        <FormControlLabel
                            key={column.id}
                            control={
                                <Checkbox
                                    checked={column.visible}
                                    onChange={(e) => {
                                        e.stopPropagation();
                                        handleColumnToggle(column.id);
                                    }}
                                    size="small"
                                    onClick={(e) => e.stopPropagation()}
                                />
                            }
                            label={column.label}
                            onClick={(e) => e.stopPropagation()}
                            sx={{
                                '& .MuiFormControlLabel-label': {
                                    fontSize: '0.875rem'
                                }
                            }}
                        />
                    ))}
                </FormGroup>
            </Box>
        </Popover>
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
                <Box sx={{ display: 'flex', gap: 1 }}>
                    {viewMode === 'card' ? (
                        <>
                            <IconButton
                                size="small"
                                onClick={(e) => setCardSortAnchor(e.currentTarget)}
                                sx={{
                                    bgcolor: Boolean(cardSortAnchor) ? 'action.selected' : 'transparent',
                                }}
                            >
                                <SortIcon />
                            </IconButton>
                            <IconButton
                                size="small"
                                onClick={(e) => setCardFieldsAnchor(e.currentTarget)}
                                sx={{
                                    bgcolor: Boolean(cardFieldsAnchor) ? 'action.selected' : 'transparent',
                                }}
                            >
                                <ViewColumnIcon />
                            </IconButton>
                        </>
                    ) : (
                        <IconButton
                            onClick={(e) => setColumnSelectorAnchor(e.currentTarget)}
                            size="small"
                            sx={{
                                bgcolor: Boolean(columnSelectorAnchor) ? 'action.selected' : 'transparent',
                            }}
                        >
                            <ViewColumnIcon />
                        </IconButton>
                    )}
                </Box>
            </Box>

            <ColumnSelector />
            <CardSortMenu />
            <CardFieldsMenu />

            {viewMode === 'card' ? (
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
                                        }
                                    }}
                                >
                                    <Box
                                        component="img"
                                        src={getImageUrl(image)}
                                        alt={image.mainRepresentation.storage.path}
                                        sx={{
                                            width: '100%',
                                            height: 200,
                                            objectFit: 'cover',
                                            backgroundColor: 'rgba(0,0,0,0.03)'
                                        }}
                                    />
                                    <Box sx={{ p: 2 }}>
                                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                                            {cardFields.map(field => field.visible && (
                                                <Box key={field.id}>
                                                    <Typography
                                                        variant="caption"
                                                        color="text.secondary"
                                                    >
                                                        {field.label}:
                                                    </Typography>
                                                    <Typography variant="body2">
                                                        {renderCardField(field.id, image)}
                                                    </Typography>
                                                </Box>
                                            ))}
                                            <Box sx={{
                                                display: 'flex',
                                                justifyContent: 'flex-end',
                                                gap: 1,
                                                mt: 1
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
                        </Grid>
                    ))}
                </Grid>
            ) : (
                renderTableView()
            )}

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

            {renderMenu()}

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
                isLoading={deleteAsset.isPending}
            />

            {viewMode === 'card' && (
                <RenameDialog
                    open={isRenameDialogOpen}
                    title="Rename Asset"
                    currentName={selectedImage?.mainRepresentation.storage.path || ''}
                    onConfirm={handleRenameConfirm}
                    onCancel={() => {
                        setIsRenameDialogOpen(false);
                        setSelectedImage(null);
                    }}
                    isLoading={renameAsset.isPending}
                />
            )}
        </Box>
    );
};

export default ImageResults;