import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
    Box,
    Typography,
    CircularProgress,
    useTheme,
    alpha,
} from '@mui/material';
import { useAssetExplorer } from '../../api/hooks/useAssetExplorer';
import { formatFileSize } from '../../utils/fileSize';
import { formatDate } from '../../utils/dateFormat';
import { type SortingState } from '@tanstack/react-table';
import { type AssetTableColumn } from '@/types/shared/assetComponents';
import AssetDisplay from '../../components/shared/AssetDisplay';
import { useNavigate } from 'react-router-dom';

interface AssetExplorerProps {
    storageIdentifier?: string;
}

export const AssetExplorer: React.FC<AssetExplorerProps> = ({ 
    storageIdentifier = ''
}) => {
    const { t } = useTranslation();
    const theme = useTheme();
    const navigate = useNavigate();
    
    // State for display options
    const [viewMode, setViewMode] = useState<'card' | 'table'>('card');
    const [cardSize, setCardSize] = useState<'small' | 'medium' | 'large'>('medium');
    const [aspectRatio, setAspectRatio] = useState<'vertical' | 'square' | 'horizontal'>('square');
    const [thumbnailScale, setThumbnailScale] = useState<'fit' | 'fill'>('fit');
    const [showMetadata, setShowMetadata] = useState(true);
    const [groupByType, setGroupByType] = useState(false);
    const [page, setPage] = useState(1);
    const [pageSize, setPageSize] = useState(25);
    const [sorting, setSorting] = useState<SortingState>([]);
    
    // Card fields configuration
    const [cardFields, setCardFields] = useState([
        { id: 'name', label: 'Name', visible: true },
        { id: 'type', label: 'Type', visible: true },
        { id: 'format', label: 'Format', visible: true },
        { id: 'size', label: 'Size', visible: true },
        { id: 'date', label: 'Date', visible: true },
    ]);

    // Table columns configuration
    const [columns, setColumns] = useState<AssetTableColumn<any>[]>([
        {
            id: 'name',
            label: 'Name',
            visible: true,
            minWidth: 200,
            accessorFn: (row: any) => row.filename,
            cell: (info: any) => info.getValue(),
            sortable: true,
            sortingFn: (rowA: any, rowB: any) => rowA.original.filename.localeCompare(rowB.original.filename)
        },
        {
            id: 'type',
            label: 'Type',
            visible: true,
            minWidth: 100,
            accessorFn: (row: any) => {
                const extension = row.filename.split('.').pop()?.toLowerCase() || '';
                if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(extension)) return 'Image';
                if (['mp4', 'mov', 'avi', 'webm'].includes(extension)) return 'Video';
                if (['mp3', 'wav', 'ogg'].includes(extension)) return 'Audio';
                return 'Document';
            },
            sortable: true
        },
        {
            id: 'format',
            label: 'Format',
            visible: true,
            minWidth: 100,
            accessorFn: (row: any) => row.filename.split('.').pop()?.toUpperCase() || '',
            sortable: true
        },
        {
            id: 'size',
            label: 'Size',
            visible: true,
            minWidth: 100,
            accessorFn: (row: any) => row.size,
            cell: (info: any) => formatFileSize(info.getValue()),
            sortable: true,
            sortingFn: (rowA: any, rowB: any) => rowA.original.size - rowB.original.size
        },
        {
            id: 'date',
            label: 'Date',
            visible: true,
            minWidth: 150,
            accessorFn: (row: any) => row.lastModified,
            cell: (info: any) => formatDate(info.getValue()),
            sortable: true,
            sortingFn: (rowA: any, rowB: any) => {
                const a = new Date(rowA.original.lastModified).getTime();
                const b = new Date(rowB.original.lastModified).getTime();
                return a - b;
            }
        }
    ]);
    
    // Use the asset explorer hook to get objects
    const { data: explorerResponse, isLoading, error } = useAssetExplorer({
        storageIdentifier,
        page,
        pageSize
    });
    
    // Extract results from the explorer response
    const files = explorerResponse?.data?.items || [];
    const totalCount = explorerResponse?.data?.totalItems || 0;
    
    // Get asset type based on file extension
    const getAssetType = (filename: string) => {
        const extension = filename.split('.').pop()?.toLowerCase() || '';
        if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(extension)) return 'Image';
        if (['mp4', 'mov', 'avi', 'webm'].includes(extension)) return 'Video';
        if (['mp3', 'wav', 'ogg'].includes(extension)) return 'Audio';
        return 'Document';
    };
    
    // Handle view mode change
    const handleViewModeChange = (_: React.MouseEvent<HTMLElement>, newMode: 'card' | 'table' | null) => {
        if (newMode) setViewMode(newMode);
    };

    // Handle card field toggle
    const handleCardFieldToggle = (fieldId: string) => {
        setCardFields(prev => prev.map(field =>
            field.id === fieldId ? { ...field, visible: !field.visible } : field
        ));
    };

    // Handle column toggle
    const handleColumnToggle = (columnId: string) => {
        setColumns(prev => prev.map(column =>
            column.id === columnId ? { ...column, visible: !column.visible } : column
        ));
    };
    
    // Handle asset click
    const handleAssetClick = (asset: any) => {
        const assetType = getAssetType(asset.filename).toLowerCase();
        navigate(`/${assetType}s/${asset.id}`, {
            state: { 
                assetType: getAssetType(asset.filename),
                storageIdentifier
            }
        });
    };
    
    // Get field value for card display
    const getFieldValue = (fieldId: string, asset: any) => {
        switch (fieldId) {
            case 'name':
                return asset.filename;
            case 'type':
                return getAssetType(asset.filename);
            case 'format':
                return asset.filename.split('.').pop()?.toUpperCase() || '';
            case 'size':
                return formatFileSize(asset.size || 0);
            case 'date':
                return formatDate(asset.lastModified);
            default:
                return '';
        }
    };
    
    return (
        <Box sx={{ 
            height: '100%', 
            display: 'flex', 
            flexDirection: 'column',
            overflow: 'hidden' // Prevent outer container from scrolling
        }}>
            {/* Content area with fixed height and controlled overflow */}
            <Box sx={{ 
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden', // Container doesn't scroll
                p: 2 
            }}>
                {isLoading ? (
                    <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
                        <CircularProgress />
                    </Box>
                ) : (
                    <AssetDisplay
                        assets={files}
                        totalCount={totalCount}
                        page={page}
                        pageSize={pageSize}
                        viewMode={viewMode}
                        cardSize={cardSize}
                        aspectRatio={aspectRatio}
                        thumbnailScale={thumbnailScale}
                        showMetadata={showMetadata}
                        groupByType={groupByType}
                        cardFields={cardFields}
                        columns={columns}
                        sorting={sorting}
                        getId={(asset) => asset.id}
                        getName={(asset) => asset.filename}
                        getType={(asset) => getAssetType(asset.filename)}
                        getThumbnailUrl={(asset) => {
                            return asset.thumbnailUrl || `/placeholder-${getAssetType(asset.filename).toLowerCase()}.png`;
                        }}
                        getProxyUrl={(asset) => {
                            return asset.presignedUrl;
                        }}
                        getField={getFieldValue}
                        onAssetClick={handleAssetClick}
                        onPageChange={setPage}
                        onPageSizeChange={setPageSize}
                        onViewModeChange={handleViewModeChange}
                        onCardSizeChange={setCardSize}
                        onAspectRatioChange={setAspectRatio}
                        onThumbnailScaleChange={setThumbnailScale}
                        onShowMetadataChange={setShowMetadata}
                        onGroupByTypeChange={setGroupByType}
                        onCardFieldToggle={handleCardFieldToggle}
                        onColumnToggle={handleColumnToggle}
                        onSortChange={setSorting}
                        title="Assets"
                        error={error ? { status: 'Error', message: error.message } : null}
                        isLoading={isLoading}
                    />
                )}
            </Box>
        </Box>
    );
};

export default AssetExplorer;
