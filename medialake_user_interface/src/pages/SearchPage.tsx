import React, { useState, useEffect, useCallback } from 'react';
import { formatDate } from '@/utils/dateFormat';
import {
    Box,
    Typography,
    LinearProgress,
    Paper,
    Menu,
    MenuItem,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogContentText,
    DialogActions,
    Button
} from '@mui/material';
import SearchOffIcon from '@mui/icons-material/SearchOff';
import { RightSidebar, RightSidebarProvider } from '../components/common/RightSidebar';
import SearchFilters from '../components/search/SearchFilters';
import UnifiedResultsView from '../components/search/UnifiedResultsView';
import { useSearch } from '../api/hooks/useSearch';
import { useAssetOperations } from '@/hooks/useAssetOperations';
import { type AssetBase, type ImageItem, type VideoItem, type AudioItem } from '@/types/search/searchResults';
import { type SortingState, type ColumnDef, type CellContext } from '@tanstack/react-table';
import { type AssetTableColumn } from '@/types/shared/assetComponents';
import { SearchError } from '@/api/hooks/useSearch';

type AssetItem = ImageItem | VideoItem | AudioItem;
import { useLocation, useSearchParams, useNavigate } from 'react-router-dom';
import { alpha } from '@mui/material/styles';

interface LocationState {
    query?: string;
    isSemantic?: boolean;
    preserveSearch?: boolean;
    viewMode?: 'card' | 'table';
    cardSize?: 'small' | 'medium' | 'large';
    aspectRatio?: 'vertical' | 'square' | 'horizontal';
    thumbnailScale?: 'fit' | 'fill';
    showMetadata?: boolean;
    groupByType?: boolean;
}

interface Filters {
    mediaTypes: {
        videos: boolean;
        images: boolean;
        audio: boolean;
    };
    time: {
        recent: boolean;
        lastWeek: boolean;
        lastMonth: boolean;
        lastYear: boolean;
    };
}

const DEFAULT_PAGE_SIZE = 50;

const SearchPage: React.FC = () => {
    const location = useLocation();
    const { query, isSemantic } = (location.state as LocationState) || {};
    const [searchParams, setSearchParams] = useSearchParams();
    const currentPage = parseInt(searchParams.get('page') || '1', 10);
    const currentQuery = searchParams.get('q') || query || '';
    const currentSemantic = searchParams.get('semantic') === 'true' || isSemantic || false;
    const navigate = useNavigate();

    const [pageSize, setPageSize] = useState<number>(
        parseInt(searchParams.get('pageSize') || DEFAULT_PAGE_SIZE.toString(), 10)
    );

    const {
        data: searchResults,
        isLoading,
        isFetching,
        error
    } = useSearch(currentQuery, {
        page: currentPage,
        pageSize: pageSize,
        isSemantic: currentSemantic
    });

    const [filters, setFilters] = useState<Filters>({
        mediaTypes: {
            videos: true,
            images: true,
            audio: true,
        },
        time: {
            recent: false,
            lastWeek: false,
            lastMonth: false,
            lastYear: false,
        }
    });

    const [viewMode, setViewMode] = useState<'card' | 'table'>(
        location.state?.preserveSearch ? location.state.viewMode : 'card'
    );
    const [cardSize, setCardSize] = useState<'small' | 'medium' | 'large'>(
        location.state?.preserveSearch ? location.state.cardSize : 'medium'
    );
    const [aspectRatio, setAspectRatio] = useState<'vertical' | 'square' | 'horizontal'>(
        location.state?.preserveSearch ? location.state.aspectRatio : 'square'
    );
    const [thumbnailScale, setThumbnailScale] = useState<'fit' | 'fill'>(
        location.state?.preserveSearch ? location.state.thumbnailScale : 'fit'
    );
    const [showMetadata, setShowMetadata] = useState(
        location.state?.preserveSearch ? location.state.showMetadata : true
    );
    const [groupByType, setGroupByType] = useState(
        location.state?.preserveSearch ? location.state.groupByType : false
    );

    const [sorting, setSorting] = useState<SortingState>([]);
    const [editingAssetId, setEditingAssetId] = useState<string>();
    const [editedName, setEditedName] = useState<string>();

    const {
        handleDeleteClick,
        handleMenuOpen,
        handleStartEditing,
        handleNameChange,
        handleNameEditComplete,
        handleMenuClose,
        handleAction,
        handleDeleteConfirm,
        handleDeleteCancel,
        editingAssetId: currentEditingAssetId,
        editedName: currentEditedName,
        isDeleteModalOpen,
        menuAnchorEl,
        selectedAsset,
    } = useAssetOperations<AssetItem>();

    const handleAssetClick = useCallback((asset: AssetItem) => {
        const assetType = asset.DigitalSourceAsset.Type.toLowerCase();
        navigate(`/${assetType}s/${asset.InventoryID}`, {
            state: { 
                assetType: asset.DigitalSourceAsset.Type,
                searchTerm: currentQuery
            }
        });
    }, [navigate, currentQuery]);

    useEffect(() => {
        setEditingAssetId(currentEditingAssetId || undefined);
        setEditedName(currentEditedName);
    }, [currentEditingAssetId, currentEditedName]);

    const formatFileSize = (sizeInBytes: number) => {
        const sizes = ['B', 'KB', 'MB', 'GB'];
        let i = 0;
        let size = sizeInBytes;
        while (size >= 1024 && i < sizes.length - 1) {
            size /= 1024;
            i++;
        }
        return `${Math.round(size * 100) / 100} ${sizes[i]}`;
    };

    const [cardFields, setCardFields] = useState([
        { id: 'name', label: 'Object Name', visible: true },
        { id: 'type', label: 'Type', visible: true },
        { id: 'format', label: 'Format', visible: true },
        { id: 'createdAt', label: 'Date Created', visible: true },
    ]);

    const [columns, setColumns] = useState<AssetTableColumn<AssetItem>[]>([
        {
            id: 'name',
            label: 'Name',
            visible: true,
            minWidth: 200,
            accessorFn: (row: AssetItem) => row.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name,
            cell: (info: CellContext<AssetItem, unknown>) => info.getValue() as string,
            sortable: true,
            sortingFn: (rowA, rowB) => rowA.original.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name.localeCompare(
                rowB.original.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name
            )
        },
        {
            id: 'type',
            label: 'Type',
            visible: true,
            minWidth: 100,
            accessorFn: (row: AssetItem) => row.DigitalSourceAsset.Type,
            sortable: true,
            sortingFn: (rowA, rowB) => rowA.original.DigitalSourceAsset.Type.localeCompare(rowB.original.DigitalSourceAsset.Type)
        },
        {
            id: 'format',
            label: 'Format',
            visible: true,
            minWidth: 100,
            accessorFn: (row: AssetItem) => row.DigitalSourceAsset.MainRepresentation.Format,
            sortable: true,
            sortingFn: (rowA, rowB) => rowA.original.DigitalSourceAsset.MainRepresentation.Format.localeCompare(rowB.original.DigitalSourceAsset.MainRepresentation.Format)
        },
        {
            id: 'size',
            label: 'Size',
            visible: true,
            minWidth: 100,
            accessorFn: (row: AssetItem) => row.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size,
            cell: (info: CellContext<AssetItem, unknown>) => formatFileSize(info.getValue() as number),
            sortable: true,
            sortingFn: (rowA, rowB) => {
                const a = rowA.original.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size;
                const b = rowB.original.DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size;
                return a - b;
            }
        },
        {
            id: 'date',
            label: 'Date Created',
            visible: true,
            minWidth: 150,
            accessorFn: (row: AssetItem) => row.DigitalSourceAsset.CreateDate,
            cell: (info: CellContext<AssetItem, unknown>) => {
                return formatDate(info.getValue() as string);
            },
            sortable: true,
            sortingFn: (rowA, rowB) => {
                const a = new Date(rowA.original.DigitalSourceAsset.CreateDate).getTime();
                const b = new Date(rowB.original.DigitalSourceAsset.CreateDate).getTime();
                return a - b;
            }
        }
    ]);

    const handleViewModeChange = (_: React.MouseEvent<HTMLElement>, newMode: 'card' | 'table' | null) => {
        if (newMode) setViewMode(newMode);
    };

    const handleCardFieldToggle = (fieldId: string) => {
        setCardFields(prev => prev.map(field =>
            field.id === fieldId ? { ...field, visible: !field.visible } : field
        ));
    };

    const handleColumnToggle = (columnId: string) => {
        setColumns(prev => prev.map(column =>
            column.id === columnId ? { ...column, visible: !column.visible } : column
        ));
    };

    const filteredResults = searchResults?.data?.results?.filter(item => {
        const isImage = item.DigitalSourceAsset.Type === 'Image' && filters.mediaTypes.images;
        const isVideo = item.DigitalSourceAsset.Type === 'Video' && filters.mediaTypes.videos;
        const isAudio = item.DigitalSourceAsset.Type === 'Audio' && filters.mediaTypes.audio;

        // Time-based filtering
        const createdAt = new Date(item.DigitalSourceAsset.CreateDate);
        const now = new Date();
        const timeDiff = now.getTime() - createdAt.getTime();
        const isRecent = filters.time.recent && (timeDiff <= 24 * 60 * 60 * 1000);
        const isLastWeek = filters.time.lastWeek && (timeDiff <= 7 * 24 * 60 * 60 * 1000);
        const isLastMonth = filters.time.lastMonth && (timeDiff <= 30 * 24 * 60 * 60 * 1000);
        const isLastYear = filters.time.lastYear && (timeDiff <= 365 * 24 * 60 * 60 * 1000);

        const passesTimeFilter = !filters.time.recent && !filters.time.lastWeek && !filters.time.lastMonth && !filters.time.lastYear ||
            isRecent || isLastWeek || isLastMonth || isLastYear;

        return (isImage || isVideo || isAudio) && passesTimeFilter;
    }) || [];

    const imageResults = filteredResults.filter(item => item.DigitalSourceAsset.Type === 'Image');
    const videoResults = filteredResults.filter(item => item.DigitalSourceAsset.Type === 'Video');
    const audioResults = filteredResults.filter(item => item.DigitalSourceAsset.Type === 'Audio');

    const [expandedSections, setExpandedSections] = useState({
        mediaTypes: true,
        time: true,
        status: true,
    });

    useEffect(() => {
        if ((query && !searchParams.has('q')) || (isSemantic !== undefined && !searchParams.has('semantic'))) {
            setSearchParams(prev => {
                const newParams = new URLSearchParams(prev);
                if (query && !prev.has('q')) {
                    newParams.set('q', query);
                }
                if (isSemantic !== undefined && !prev.has('semantic')) {
                    newParams.set('semantic', isSemantic.toString());
                }
                if (!prev.has('page')) {
                    newParams.set('page', '1');
                }
                return newParams;
            });
        }
    }, [query, isSemantic, searchParams, setSearchParams]);

    const handleFilterChange = (section: keyof Filters, filter: string) => {
        setFilters(prev => {
            const newFilters = { ...prev };
            if (section === 'time') {
                // Reset all time filters
                Object.keys(newFilters.time).forEach(key => {
                    newFilters.time[key as keyof typeof newFilters.time] = false;
                });
            }
            (newFilters[section] as any)[filter] = !(prev[section] as any)[filter];
            return newFilters;
        });
    };

    const handleSectionToggle = (section: string) => {
        setExpandedSections(prev => ({
            ...prev,
            [section]: !prev[section as keyof typeof prev]
        }));
    };

    const handleSearch = (params: { page: number }) => {
        let timeFilter = '';
        if (filters.time.recent) timeFilter = 'recent';
        if (filters.time.lastWeek) timeFilter = 'lastWeek';
        if (filters.time.lastMonth) timeFilter = 'lastMonth';
        if (filters.time.lastYear) timeFilter = 'lastYear';

        setSearchParams(prev => {
            const newParams = new URLSearchParams(prev);
            newParams.set('page', params.page.toString());
            if (currentQuery) {
                newParams.set('q', currentQuery);
            }
            if (timeFilter) {
                newParams.set('time', timeFilter);
            }
            if (currentSemantic) {
                newParams.set('semantic', 'true');
            }
            return newParams;
        });
    };

    const handlePageSizeChange = (newPageSize: number) => {
        setPageSize(newPageSize);
        // Reset to first page when changing page size
        setSearchParams(prev => {
            prev.set('pageSize', newPageSize.toString());
            prev.set('page', '1');
            return prev;
        });
    };

    return (
        <RightSidebarProvider>
            <>
                <Box sx={{
                    display: 'flex',
                    minHeight: '100%',
                    bgcolor: 'background.default',
                    position: 'relative',
                    overflow: 'auto'
                }}>
                    {isFetching && (
                        <LinearProgress
                            sx={{
                                position: 'fixed',
                                top: 0,
                                left: 0,
                                right: 0,
                                zIndex: 9999
                            }}
                        />
                    )}

                    {/* Main Content */}
                    <Box sx={{
                        flexGrow: 1,
                        px: 4,
                        py: 4,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 6,
                        minHeight: 0,
                        marginBottom: 4
                    }}>
                        {searchResults?.data?.searchMetadata?.totalResults === 0 && currentQuery && (
                            <Box
                                sx={{
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    minHeight: '50vh',
                                    textAlign: 'center',
                                    gap: 2
                                }}
                            >
                                <Paper
                                    elevation={0}
                                    sx={{
                                        p: 4,
                                        display: 'flex',
                                        flexDirection: 'column',
                                        alignItems: 'center',
                                        gap: 2,
                                        bgcolor: 'background.paper',
                                        borderRadius: 2
                                    }}
                                >
                                    <SearchOffIcon
                                        sx={{
                                            fontSize: 64,
                                            color: 'text.secondary',
                                            mb: 2
                                        }}
                                    />
                                    <Typography variant="h5" color="text.primary" gutterBottom>
                                        No results found
                                    </Typography>
                                    <Typography variant="body1" color="text.secondary">
                                        We couldn't find any matches for "{currentQuery}"
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                                        Try adjusting your search or filters to find what you're looking for
                                    </Typography>
                                </Paper>
                            </Box>
                        )}

                        {filteredResults.length > 0 && searchResults?.data?.searchMetadata && !error && (
                            <UnifiedResultsView
                                results={filteredResults}
                                searchMetadata={{
                                    totalResults: searchResults.data.searchMetadata.totalResults || 0,
                                    page: currentPage,
                                    pageSize: pageSize,
                                }}
                                onPageChange={(newPage) => handleSearch({ page: newPage })}
                                onPageSizeChange={handlePageSizeChange}
                                searchTerm={currentQuery}
                                groupByType={groupByType}
                                onGroupByTypeChange={setGroupByType}
                                viewMode={viewMode}
                                onViewModeChange={handleViewModeChange}
                                cardSize={cardSize}
                                onCardSizeChange={setCardSize}
                                aspectRatio={aspectRatio}
                                onAspectRatioChange={setAspectRatio}
                                thumbnailScale={thumbnailScale}
                                onThumbnailScaleChange={setThumbnailScale}
                                showMetadata={showMetadata}
                                onShowMetadataChange={setShowMetadata}
                                sorting={sorting}
                                onSortChange={setSorting}
                                cardFields={cardFields}
                                onCardFieldToggle={handleCardFieldToggle}
                                columns={columns}
                                onColumnToggle={handleColumnToggle}
                                onAssetClick={handleAssetClick}
                                onDeleteClick={handleDeleteClick}
                                onMenuClick={handleMenuOpen}
                                onEditClick={handleStartEditing}
                                onEditNameChange={handleNameChange}
                                onEditNameComplete={handleNameEditComplete}
                                editingAssetId={editingAssetId}
                                editedName={editedName}
                            />
                        )}

                        {error && (
                            <UnifiedResultsView
                                results={[]}
                                searchMetadata={{
                                    totalResults: 0,
                                    page: currentPage,
                                    pageSize: pageSize,
                                }}
                                onPageChange={(newPage) => handleSearch({ page: newPage })}
                                onPageSizeChange={handlePageSizeChange}
                                searchTerm={currentQuery}
                                groupByType={groupByType}
                                onGroupByTypeChange={setGroupByType}
                                viewMode={viewMode}
                                onViewModeChange={handleViewModeChange}
                                cardSize={cardSize}
                                onCardSizeChange={setCardSize}
                                aspectRatio={aspectRatio}
                                onAspectRatioChange={setAspectRatio}
                                thumbnailScale={thumbnailScale}
                                onThumbnailScaleChange={setThumbnailScale}
                                showMetadata={showMetadata}
                                onShowMetadataChange={setShowMetadata}
                                sorting={sorting}
                                onSortChange={setSorting}
                                cardFields={cardFields}
                                onCardFieldToggle={handleCardFieldToggle}
                                columns={columns}
                                onColumnToggle={handleColumnToggle}
                                onAssetClick={handleAssetClick}
                                onDeleteClick={handleDeleteClick}
                                onMenuClick={handleMenuOpen}
                                onEditClick={handleStartEditing}
                                onEditNameChange={handleNameChange}
                                onEditNameComplete={handleNameEditComplete}
                                editingAssetId={editingAssetId}
                                editedName={editedName}
                                error={{
                                    status: (error as SearchError).apiResponse?.status || error.name,
                                    message: (error as SearchError).apiResponse?.message || error.message
                                }}
                                isLoading={isLoading || isFetching}
                            />
                        )}
                    </Box>

                    <RightSidebar>
                        <SearchFilters
                            filters={filters}
                            expandedSections={expandedSections}
                            onFilterChange={handleFilterChange}
                            onSectionToggle={handleSectionToggle}
                            groupByType={groupByType}
                            onGroupByTypeChange={setGroupByType}
                        />
                    </RightSidebar>
                </Box>

                {/* Asset Menu */}
                <Menu
                    anchorEl={menuAnchorEl}
                    open={Boolean(menuAnchorEl)}
                    onClose={handleMenuClose}
                    MenuListProps={{
                        'aria-labelledby': selectedAsset ? `asset-menu-button-${selectedAsset.InventoryID}` : undefined
                    }}
                    anchorOrigin={{
                        vertical: 'bottom',
                        horizontal: 'right',
                    }}
                    transformOrigin={{
                        vertical: 'top',
                        horizontal: 'right',
                    }}
                    PaperProps={{
                        elevation: 0,
                        sx: {
                            borderRadius: '8px',
                            minWidth: 200,
                            mt: 1,
                            border: theme => `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                            backgroundColor: theme => theme.palette.background.paper,
                            overflow: 'visible',
                            position: 'fixed',
                            zIndex: 1400,
                        },
                    }}
                    slotProps={{
                        paper: {
                            sx: {
                                overflow: 'visible',
                                position: 'fixed',
                            }
                        }
                    }}
                >
                    <MenuItem onClick={() => handleAction('rename')}>Rename</MenuItem>
                    <MenuItem onClick={() => handleAction('share')}>Share</MenuItem>
                    <MenuItem onClick={() => handleAction('download')}>Download</MenuItem>
                </Menu>

                {/* Delete Confirmation Dialog */}
                <Dialog
                    open={isDeleteModalOpen}
                    onClose={handleDeleteCancel}
                    aria-labelledby="delete-dialog-title"
                    aria-describedby="delete-dialog-description"
                >
                    <DialogTitle id="delete-dialog-title">
                        Confirm Delete
                    </DialogTitle>
                    <DialogContent>
                        <DialogContentText id="delete-dialog-description">
                            Are you sure you want to delete this asset? This action cannot be undone.
                        </DialogContentText>
                    </DialogContent>
                    <DialogActions>
                        <Button onClick={handleDeleteCancel}>Cancel</Button>
                        <Button onClick={handleDeleteConfirm} color="error" autoFocus>
                            Delete
                        </Button>
                    </DialogActions>
                </Dialog>
            </>
        </RightSidebarProvider>
    );
};

export default SearchPage;
