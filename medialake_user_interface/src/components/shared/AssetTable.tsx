import React from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Box,
  TextField,
  InputAdornment,
  Avatar,
  Typography,
  useTheme,
  alpha,
  Tooltip,
  Chip
} from '@mui/material';
import {
  Delete as DeleteIcon,
  MoreVert as MoreVertIcon,
  Edit as EditIcon,
  Check as CheckIcon,
  Close as CloseIcon,
  ArrowUpward as ArrowUpwardIcon,
  ArrowDownward as ArrowDownwardIcon,
  FilterList as FilterListIcon
} from '@mui/icons-material';
import { SortingState } from '@tanstack/react-table';
import { AssetTableColumn } from '@/types/shared/assetComponents';

export interface AssetTableProps<T> {
  data: T[];
  columns: AssetTableColumn<T>[];
  sorting: SortingState;
  onSortingChange: (sorting: SortingState) => void;
  onDeleteClick: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  onMenuClick: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  onEditClick: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  onAssetClick: (asset: T) => void;
  getThumbnailUrl: (asset: T) => string | undefined;
  getName: (asset: T) => string;
  getId: (asset: T) => string;
  getAssetType: (asset: T) => string;
  editingId?: string | null;
  editedName?: string;
  onEditNameChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onEditNameComplete: (asset: T) => void;
  onFilterClick?: (event: React.MouseEvent<HTMLElement>, columnId: string) => void;
  activeFilters?: Array<{ columnId: string; value: string }>;
  onRemoveFilter?: (columnId: string) => void;
}

export function AssetTable<T>({
  data,
  columns,
  sorting,
  onSortingChange,
  onDeleteClick,
  onMenuClick,
  onEditClick,
  onAssetClick,
  getThumbnailUrl,
  getName,
  getId,
  getAssetType,
  editingId,
  editedName,
  onEditNameChange,
  onEditNameComplete,
  onFilterClick,
  activeFilters = [],
  onRemoveFilter
}: AssetTableProps<T>) {
  const theme = useTheme();

  const handleSort = (columnId: string) => {
    const currentSort = sorting[0];
    const desc = currentSort?.id === columnId ? !currentSort.desc : false;
    onSortingChange([{ id: columnId, desc }]);
  };

  const handleKeyDown = (asset: T, event: React.KeyboardEvent) => {
    if (event.key === 'Enter') {
      onEditNameComplete(asset);
    } else if (event.key === 'Escape') {
      onEditNameComplete(asset);
    }
  };

  return (
    <TableContainer component={Paper} elevation={0} sx={{ borderRadius: 2 }}>
      <Table sx={{ minWidth: 650 }} aria-label="assets table">
        <TableHead>
          <TableRow>
            <TableCell sx={{ width: 60 }}></TableCell>
            {columns
              .filter((column) => column.visible)
              .map((column) => (
                <TableCell
                  key={column.id}
                  sx={{
                    minWidth: column.minWidth,
                    cursor: column.sortable ? 'pointer' : 'default',
                    userSelect: 'none',
                    '&:hover': {
                      backgroundColor: column.sortable
                        ? alpha(theme.palette.primary.main, 0.05)
                        : 'inherit',
                    },
                  }}
                  onClick={() => column.sortable && handleSort(column.id)}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 0.5,
                    }}
                  >
                    {column.label}
                    {column.sortable &&
                      sorting.some((sort) => sort.id === column.id) && (
                        <Box component="span" sx={{ display: 'inline-flex' }}>
                          {sorting.find((sort) => sort.id === column.id)
                            ?.desc ? (
                            <ArrowDownwardIcon
                              fontSize="small"
                              sx={{ fontSize: '0.85rem' }}
                            />
                          ) : (
                            <ArrowUpwardIcon
                              fontSize="small"
                              sx={{ fontSize: '0.85rem' }}
                            />
                          )}
                        </Box>
                      )}
                    
                    {onFilterClick && (
                      <IconButton
                        size="small"
                        onClick={(e) => {
                          e.stopPropagation();
                          onFilterClick(e, column.id);
                        }}
                        sx={{ ml: 0.5, p: 0.25 }}
                      >
                        <FilterListIcon fontSize="small" sx={{ fontSize: '0.85rem' }} />
                      </IconButton>
                    )}
                  </Box>
                  
                  {activeFilters && activeFilters.some(f => f.columnId === column.id) && (
                    <Box sx={{ mt: 0.5 }}>
                      {activeFilters
                        .filter(f => f.columnId === column.id)
                        .map((filter, index) => (
                          <Chip
                            key={index}
                            label={filter.value}
                            size="small"
                            onDelete={() => onRemoveFilter && onRemoveFilter(filter.columnId)}
                            sx={{ mr: 0.5, height: 20, fontSize: '0.7rem' }}
                          />
                        ))}
                    </Box>
                  )}
                </TableCell>
              ))}
            <TableCell align="right" sx={{ width: 120 }}>
              Actions
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {data.map((row) => (
            <TableRow
              key={getId(row)}
              sx={{
                '&:hover': {
                  backgroundColor: alpha(theme.palette.primary.main, 0.05),
                },
                cursor: 'pointer',
              }}
              onClick={() => onAssetClick(row)}
            >
              <TableCell
                sx={{ width: 60, p: 1 }}
                onClick={(e) => e.stopPropagation()}
              >
                <Avatar
                  variant="rounded"
                  src={getThumbnailUrl(row)}
                  alt={getName(row)}
                  sx={{ width: 40, height: 40 }}
                >
                  {getName(row).charAt(0).toUpperCase()}
                </Avatar>
              </TableCell>
              {columns
                .filter((column) => column.visible)
                .map((column) => (
                  <TableCell key={column.id}>
                    {column.id === 'name' && editingId === getId(row) ? (
                      <TextField
                        fullWidth
                        variant="outlined"
                        size="small"
                        value={editedName}
                        onChange={onEditNameChange}
                        onKeyDown={(e) => handleKeyDown(row, e)}
                        autoFocus
                        onClick={(e) => e.stopPropagation()}
                        InputProps={{
                          endAdornment: (
                            <InputAdornment position="end">
                              <IconButton
                                size="small"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onEditNameComplete(row);
                                }}
                                edge="end"
                              >
                                <CheckIcon fontSize="small" />
                              </IconButton>
                              <IconButton
                                size="small"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onEditNameComplete(row);
                                }}
                                edge="end"
                              >
                                <CloseIcon fontSize="small" />
                              </IconButton>
                            </InputAdornment>
                          ),
                        }}
                      />
                    ) : column.cell ? (
                      column.cell({
                        getValue: () => column.accessorFn?.(row),
                        row: { original: row },
                      } as any)
                    ) : (
                      <Typography variant="body2">
                        {column.accessorFn?.(row)?.toString() || ''}
                      </Typography>
                    )}
                  </TableCell>
                ))}
              <TableCell
                align="right"
                sx={{ width: 120 }}
                onClick={(e) => e.stopPropagation()}
              >
                <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <Tooltip title="Edit">
                    <IconButton
                      size="small"
                      onClick={(e) => onEditClick(row, e)}
                      sx={{ color: theme.palette.text.secondary }}
                    >
                      <EditIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Delete">
                    <IconButton
                      size="small"
                      onClick={(e) => onDeleteClick(row, e)}
                      sx={{ color: theme.palette.error.main }}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="More">
                    <IconButton
                      size="small"
                      onClick={(e) => onMenuClick(row, e)}
                      id={`asset-menu-button-${getId(row)}`}
                      aria-controls={`asset-menu-${getId(row)}`}
                      aria-haspopup="true"
                      sx={{ color: theme.palette.text.secondary }}
                    >
                      <MoreVertIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </Box>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
