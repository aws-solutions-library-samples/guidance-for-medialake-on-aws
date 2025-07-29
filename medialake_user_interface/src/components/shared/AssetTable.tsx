import React, { useRef, useState, useCallback, useEffect } from "react";
import {
  Box,
  Typography,
  IconButton,
  Button,
  TableContainer,
  Checkbox,
  CircularProgress,
} from "@mui/material";
import { InlineTextEditor } from "../common/InlineTextEditor";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  createColumnHelper,
  type SortingState,
  type ColumnFiltersState,
  type Row,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ResizableTable } from "../common/table";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import DownloadIcon from "@mui/icons-material/Download";
import FavoriteIcon from "@mui/icons-material/Favorite";
import FavoriteBorderIcon from "@mui/icons-material/FavoriteBorder";
import { type AssetTableColumn } from "@/types/shared/assetComponents";
import { AssetAudio } from "../asset";

export interface AssetTableProps<T> {
  data: T[];
  columns: AssetTableColumn<T>[];
  sorting: SortingState;
  onSortingChange: (sorting: SortingState) => void;
  onDeleteClick: (item: T, event: React.MouseEvent<HTMLElement>) => void;
  onDownloadClick: (item: T, event: React.MouseEvent<HTMLElement>) => void;
  onEditClick?: (item: T, event: React.MouseEvent<HTMLElement>) => void;
  onAssetClick: (item: T) => void;
  getThumbnailUrl: (item: T) => string;
  getName: (item: T) => string;
  getId: (item: T) => string;
  getAssetType?: (item: T) => string;
  editingId?: string;
  editedName?: string;
  onEditNameChange?: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onEditNameComplete?: (item: T, save: boolean, value?: string) => void;
  onFilterClick?: (
    event: React.MouseEvent<HTMLElement>,
    columnId: string,
  ) => void;
  activeFilters?: Array<{ columnId: string; value: string }>;
  onRemoveFilter?: (columnId: string) => void;
  isSelected?: (item: T) => boolean;
  onSelectToggle?: (item: T, event: React.MouseEvent<HTMLElement>) => void;
  isFavorite?: (item: T) => boolean;
  onFavoriteToggle?: (item: T, event: React.MouseEvent<HTMLElement>) => void;
  selectedSearchFields?: string[]; // Add selectedSearchFields prop
  isRenaming?: boolean; // Add isRenaming prop for loading state
  renamingAssetId?: string; // ID of the asset currently being renamed
}

export function AssetTable<T>({
  data,
  columns,
  sorting,
  onSortingChange,
  onDeleteClick,
  onDownloadClick,
  onEditClick,
  onAssetClick,
  getThumbnailUrl,
  getName,
  getId,
  getAssetType = () => "Image", // Default to Image if not provided
  editingId,
  editedName,
  onEditNameChange,
  onEditNameComplete,
  onFilterClick,
  activeFilters = [],
  onRemoveFilter,
  isSelected = () => false,
  onSelectToggle,
  isFavorite = () => false,
  onFavoriteToggle,
  selectedSearchFields,
  isRenaming = false,
  renamingAssetId,
}: AssetTableProps<T>): React.ReactElement {
  const containerRef = useRef<HTMLDivElement>(null);
  const columnHelper = createColumnHelper<T>();
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const editInputRef = useRef<HTMLInputElement>(null);
  const hasInitialFocusRef = useRef<boolean>(false);
  const preventCommitRef = useRef<boolean>(false);
  const commitRef = useRef<(() => void) | null>(null);

  // Create a mapping between API field IDs and column IDs
  const fieldMapping: Record<string, string> = {
    // Root level fields (new API structure)
    id: "id",
    assetType: "type",
    format: "format",
    createdAt: "date",
    objectName: "name",
    fileSize: "size",
    fullPath: "fullPath",
    bucket: "bucket",
    FileHash: "hash",

    // Legacy nested fields (for backward compatibility)
    "DigitalSourceAsset.Type": "type",
    "DigitalSourceAsset.MainRepresentation.Format": "format",
    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.CreateDate":
      "date",
    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.CreateDate":
      "date",
    "DigitalSourceAsset.CreateDate": "date",
    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name":
      "name",
    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileInfo.Size":
      "size",
    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileSize":
      "size",
    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.FullPath":
      "fullPath",
    "DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.Bucket":
      "bucket",
    "Metadata.Consolidated": "metadata",
    InventoryID: "id",
  };

  // Create a reverse mapping for easier lookup
  const reverseFieldMapping: Record<string, string[]> = {};
  Object.entries(fieldMapping).forEach(([apiId, colId]) => {
    if (!reverseFieldMapping[colId]) {
      reverseFieldMapping[colId] = [];
    }
    reverseFieldMapping[colId].push(apiId);
  });

  // Component initialization

  // Add state to track if all rows are selected
  const [allSelected, setAllSelected] = useState(false);
  const [someSelected, setSomeSelected] = useState(false);

  // Function to handle selecting/deselecting all rows
  const handleSelectAll = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (onSelectToggle) {
        const visibleRows = data;
        visibleRows.forEach((row) => {
          if (e.target.checked !== isSelected(row)) {
            onSelectToggle(row, e as any);
          }
        });
      }
    },
    [data, onSelectToggle, isSelected],
  );

  // Update allSelected and someSelected states when data or isSelected changes
  useEffect(() => {
    if (data.length === 0) {
      setAllSelected(false);
      setSomeSelected(false);
      return;
    }

    const selectedCount = data.filter((row) => isSelected(row)).length;
    setAllSelected(selectedCount === data.length);
    setSomeSelected(selectedCount > 0 && selectedCount < data.length);
  }, [data, isSelected]);

  const tableColumns = React.useMemo(() => {
    // Filter columns based on selectedSearchFields
    let visibleColumns = columns.filter((col) => col.visible);

    if (selectedSearchFields && selectedSearchFields.length > 0) {
      visibleColumns = visibleColumns.filter((col) => {
        // Special case for name field
        if (col.id === "name") {
          return selectedSearchFields.some(
            (field) => field.includes("Name") || field === "objectName",
          );
        }

        // Special case for date field
        if (col.id === "date") {
          return selectedSearchFields.some(
            (field) => field.includes("CreateDate") || field === "createdAt",
          );
        }

        // Special case for size field
        if (col.id === "size") {
          return selectedSearchFields.some(
            (field) =>
              field.includes("FileSize") ||
              field.includes("Size") ||
              field === "fileSize",
          );
        }

        // For other fields, check if any of their mapped API field IDs are in the selectedSearchFields
        const apiFieldIds = reverseFieldMapping[col.id] || [];
        return apiFieldIds.some((apiFieldId) =>
          selectedSearchFields.includes(apiFieldId),
        );
      });
    }

    const tableColumns = [];

    // Only include the selection checkbox column if onSelectToggle is provided
    if (onSelectToggle) {
      tableColumns.push(
        // Selection checkbox column
        // Custom header component for the select column
        columnHelper.display({
          id: "select",
          // Use a custom header component
          header: () => (
            <Box sx={{ p: 1, display: "flex", alignItems: "center", gap: 1 }}>
              <Checkbox
                size="small"
                checked={allSelected}
                indeterminate={someSelected}
                onChange={(e) => {
                  e.stopPropagation();
                  handleSelectAll(e);
                }}
                sx={{
                  padding: 0,
                  "& .MuiSvgIcon-root": {
                    fontSize: "1.2rem",
                  },
                  "&.Mui-checked": {
                    color: "primary.main",
                  },
                  "&.MuiCheckbox-indeterminate": {
                    color: "primary.main",
                  },
                }}
              />
              <Typography variant="body2" sx={{ fontWeight: "bold" }}>
                Select All
              </Typography>
            </Box>
          ),
          enableSorting: false,
          size: 100,
          cell: (info) => (
            <Box
              sx={{ p: 1, display: "flex", justifyContent: "center" }}
              className="checkbox-cell"
            >
              <Checkbox
                size="small"
                checked={isSelected(info.row.original)}
                onChange={(e) => {
                  e.stopPropagation();
                  onSelectToggle(info.row.original, e as any);
                }}
                sx={{
                  padding: 0,
                  "& .MuiSvgIcon-root": {
                    fontSize: "1.2rem",
                  },
                  "&.Mui-checked": {
                    color: "primary.main",
                  },
                }}
              />
            </Box>
          ),
        }),
      );
    }

    // Add the rest of the columns
    tableColumns.push(
      columnHelper.accessor((row) => getThumbnailUrl(row), {
        id: "preview",
        header: "Preview",
        size: 100,
        enableSorting: false,
        cell: (info) => {
          const assetType = getAssetType(info.row.original);

          if (assetType === "Audio") {
            return (
              <Box sx={{ p: 1 }}>
                <Box
                  sx={{
                    width: 60,
                    height: 60,
                    borderRadius: 1,
                    overflow: "hidden",
                  }}
                >
                  <AssetAudio
                    src={info.getValue()}
                    alt={getName(info.row.original)}
                    compact={true}
                    size="small"
                  />
                </Box>
              </Box>
            );
          }

          return (
            <Box sx={{ p: 1 }}>
              <Box
                component="img"
                src={info.getValue()}
                alt={getName(info.row.original)}
                sx={{
                  width: 60,
                  height: 60,
                  objectFit: "cover",
                  borderRadius: 1,
                  display: "block",
                }}
              />
            </Box>
          );
        },
      }),
      ...visibleColumns.map((col) =>
        columnHelper.accessor(
          (row) =>
            col.accessorFn ? col.accessorFn(row) : (row as any)[col.id],
          {
            id: col.id,
            header: col.label,
            size: col.minWidth,
            enableSorting: true,
            cell: (info) => {
              // 1) If this is the “name” column and we’re in edit mode, show the inline editor:
              if (col.id === "name" && onEditClick) {
                const rowId = getId(info.row.original);
                const isEditing = editingId === rowId;

                return (
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: isEditing ? "flex-start" : "center",
                      gap: 1,
                      p: 1,
                      width: "100%",
                    }}
                  >
                    {isEditing ? (
                      <Box
                        sx={{
                          display: "flex",
                          flexDirection: "column",
                          gap: 1,
                          width: "100%",
                        }}
                      >
                        <InlineTextEditor
                          key={rowId}
                          initialValue={editedName ?? ""}
                          editingCellId={rowId}
                          preventCommitRef={preventCommitRef}
                          commitRef={commitRef}
                          onChangeCommit={(value) =>
                            onEditNameChange?.({
                              target: { value },
                            } as React.ChangeEvent<HTMLInputElement>)
                          }
                          onComplete={(save, value) =>
                            onEditNameComplete?.(info.row.original, save, value)
                          }
                          isEditing
                          autoFocus
                          size="small"
                          sx={{
                            flex: 1,
                            minWidth: "100%",
                            "& .MuiInputBase-root": {
                              width: "100%",
                              minHeight: "2.5em",
                            },
                            "& .MuiInputBase-input": {
                              whiteSpace: "normal",
                              wordBreak: "break-word",
                            },
                          }}
                          multiline
                          fullWidth
                        />
                        <Box
                          sx={{
                            display: "flex",
                            gap: 1,
                            justifyContent: "flex-end",
                            mt: 1,
                          }}
                        >
                          <Button
                            size="small"
                            variant="contained"
                            onMouseDown={(e) => {
                              e.stopPropagation();
                              e.preventDefault();
                              console.log("💾 AssetTable Save mousedown");
                              // Set flag to prevent blur from canceling
                              preventCommitRef.current = true;
                            }}
                            onClick={(e) => {
                              e.stopPropagation();
                              e.preventDefault();
                              console.log("💾 AssetTable Save clicked");
                              console.log(
                                "💾 AssetTable commitRef.current:",
                                commitRef.current,
                              );
                              // Reset the prevent flag
                              preventCommitRef.current = false;
                              // Call the commit function directly via ref
                              if (commitRef.current) {
                                console.log(
                                  "💾 AssetTable calling commitRef.current()",
                                );
                                commitRef.current();
                              } else {
                                console.error(
                                  "💾 AssetTable commitRef.current is null!",
                                );
                              }
                            }}
                          >
                            Save
                          </Button>
                          <Button
                            size="small"
                            onMouseDown={(e) => {
                              e.stopPropagation();
                              console.log("🚫 AssetTable Cancel clicked");
                              // Set flag to prevent InlineTextEditor commit from being called
                              // Use onMouseDown instead of onClick to set the flag before onBlur
                              preventCommitRef.current = true;
                            }}
                            onClick={(e) => {
                              e.stopPropagation();
                              onEditNameComplete?.(
                                info.row.original,
                                false,
                                undefined,
                              );
                            }}
                          >
                            Cancel
                          </Button>
                        </Box>
                      </Box>
                    ) : (
                      <>
                        <Typography noWrap>{info.getValue()}</Typography>
                        <IconButton
                          size="small"
                          onClick={(e) => {
                            e.stopPropagation();
                            onEditClick(info.row.original, e);
                          }}
                          disabled={isRenaming && renamingAssetId === rowId}
                        >
                          {isRenaming && renamingAssetId === rowId ? (
                            <CircularProgress size={16} />
                          ) : (
                            <EditIcon fontSize="small" />
                          )}
                        </IconButton>
                      </>
                    )}
                  </Box>
                );
              }

              // 2) Default case for *every other* column:
              return <Box sx={{ p: 1 }}>{info.getValue()}</Box>;
            },
          },
        ),
      ),
      columnHelper.display({
        id: "actions",
        header: "Actions",
        size: 150,
        cell: (info) => (
          <Box
            sx={{ display: "flex", gap: 1, justifyContent: "flex-end", p: 1 }}
          >
            <IconButton
              size="small"
              onClick={(e) => {
                e.stopPropagation();
                if (onFavoriteToggle) {
                  onFavoriteToggle(info.row.original, e);
                }
              }}
              sx={{
                padding: "4px",
              }}
            >
              {isFavorite(info.row.original) ? (
                <FavoriteIcon fontSize="small" color="error" />
              ) : (
                <FavoriteBorderIcon fontSize="small" />
              )}
            </IconButton>
            <IconButton
              size="small"
              onClick={(e) => onDeleteClick(info.row.original, e)}
            >
              <DeleteIcon fontSize="small" />
            </IconButton>
            <IconButton
              size="small"
              onClick={(e) => onDownloadClick(info.row.original, e)}
              id={`asset-download-button-${getId(info.row.original)}`}
              sx={{
                position: "relative",
                zIndex: 1,
              }}
            >
              <DownloadIcon fontSize="small" />
            </IconButton>
          </Box>
        ),
      }),
    );

    return tableColumns;
  }, [
    columns,
    editingId,
    editedName,
    onSelectToggle,
    isSelected,
    allSelected,
    someSelected,
    handleSelectAll,
    onFavoriteToggle,
    isFavorite,
    columnHelper,
    selectedSearchFields,
    reverseFieldMapping,
  ]);

  const table = useReactTable({
    data,
    columns: tableColumns,
    getRowId: (row) => getId(row),
    state: {
      sorting,
      columnFilters,
    },
    onSortingChange,
    onColumnFiltersChange: setColumnFilters,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    filterFns: {
      includesString: (row, columnId, filterValue) => {
        const value = String(row.getValue(columnId) || "").toLowerCase();
        return value.includes(String(filterValue).toLowerCase());
      },
    },
    autoResetPageIndex: false,
    autoResetExpanded: false,
  });

  const { rows } = table.getRowModel();
  const rowVirtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => containerRef.current,
    estimateSize: () => 53,
    overscan: 20,
  });

  const handleRowClick = (row: Row<T>) => {
    if (!editingId) {
      onAssetClick(row.original);
    }
  };

  return (
    <TableContainer
      sx={{
        maxHeight: "100%",
        overflowY: "visible",
        width: "100%",
        border: "none",
        "& .MuiTable-root": {
          borderCollapse: "separate",
          borderSpacing: 0,
        },
      }}
    >
      <ResizableTable
        table={table}
        containerRef={containerRef}
        virtualizer={rowVirtualizer}
        rows={rows}
        onRowClick={handleRowClick}
        maxHeight="none"
        onFilterClick={onFilterClick}
        activeFilters={activeFilters}
        onRemoveFilter={onRemoveFilter}
      />
    </TableContainer>
  );
}

export default AssetTable;
