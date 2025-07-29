import React, { useRef, useState } from "react";
import { Box, IconButton, TextField, Button } from "@mui/material";
import EditIcon from "@mui/icons-material/Edit";
import DownloadIcon from "@mui/icons-material/Download";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  ColumnDef,
  SortingState,
  ColumnFiltersState,
  ColumnSizingState,
  ColumnResizeMode,
  Row,
} from "@tanstack/react-table";
import { useVirtualizer } from "@tanstack/react-virtual";
import { ResizableTable } from "./ResizableTable";
import { BaseTableToolbar } from "./BaseTableToolbar";
import { TableCellContent } from "./TableCellContent";
import { type AssetBase } from "@/types/search/searchResults";
import { type AssetTableColumn } from "@/types/shared/assetComponents";

interface AssetTableProps<T> {
  data: T[];
  columns: AssetTableColumn<T>[];
  onRowClick?: (item: T) => void;
  onEditName?: (asset: T, newName: string) => void;
  searchPlaceholder?: string;
  sorting?: SortingState;
  onSortingChange?: (sorting: SortingState) => void;
  columnFilters?: ColumnFiltersState;
  onColumnFiltersChange?: (filters: ColumnFiltersState) => void;
  selectedSearchFields?: string[]; // Add selectedSearchFields prop
}

export function AssetTable<T>({
  data,
  columns: userColumns,
  onRowClick,
  onEditName,
  searchPlaceholder,
  sorting = [],
  onSortingChange,
  columnFilters = [],
  onColumnFiltersChange,
  selectedSearchFields,
}: AssetTableProps<T>) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [columnVisibility, setColumnVisibility] = useState({});
  const [columnSizing, setColumnSizing] = useState<ColumnSizingState>({});
  const [globalFilter, setGlobalFilter] = useState("");
  const [columnMenuAnchor, setColumnMenuAnchor] = useState<null | HTMLElement>(
    null,
  );
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editedName, setEditedName] = useState("");

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

  // Calculate column visibility based on selectedSearchFields
  React.useEffect(() => {
    if (selectedSearchFields && selectedSearchFields.length > 0) {
      const newColumnVisibility: Record<string, boolean> = {};

      userColumns.forEach((column) => {
        const colId = column.id;

        // Special case for name field
        if (colId === "name") {
          const hasNameField = selectedSearchFields.some(
            (field) => field.includes("Name") || field === "objectName",
          );
          newColumnVisibility[colId] = hasNameField;
        }
        // Special case for date field
        else if (colId === "date") {
          const hasDateField = selectedSearchFields.some(
            (field) => field.includes("CreateDate") || field === "createdAt",
          );
          newColumnVisibility[colId] = hasDateField;
        }
        // Special case for size field
        else if (colId === "size") {
          const hasSizeField = selectedSearchFields.some(
            (field) =>
              field.includes("FileSize") ||
              field.includes("Size") ||
              field === "fileSize",
          );
          newColumnVisibility[colId] = hasSizeField;
        }
        // For other fields, check if any of their mapped API field IDs are in the selectedSearchFields
        else {
          const apiFieldIds = reverseFieldMapping[colId] || [];
          const isFieldSelected = apiFieldIds.some((apiFieldId) =>
            selectedSearchFields.includes(apiFieldId),
          );
          newColumnVisibility[colId] = isFieldSelected;
        }
      });

      setColumnVisibility(newColumnVisibility);
    } else {
      // If no selectedSearchFields, show all columns
      const allVisible: Record<string, boolean> = {};
      userColumns.forEach((column) => {
        allVisible[column.id] = true;
      });
      setColumnVisibility(allVisible);
    }
  }, [selectedSearchFields, userColumns]);

  const columns = React.useMemo(() => {
    return userColumns.map((col) => {
      if (col.id === "name") {
        return {
          ...col,
          cell: (info: any) => {
            const asset = info.row.original;
            const isEditing = editingId === asset.InventoryID;
            const currentName = info.getValue() as string;

            if (isEditing) {
              return (
                <Box
                  sx={{ display: "flex", alignItems: "center", gap: 1, p: 1 }}
                >
                  <TextField
                    value={editedName}
                    onChange={(e) => setEditedName(e.target.value)}
                    onKeyPress={(e) => {
                      if (e.key === "Enter") {
                        onEditName?.(asset, editedName);
                        setEditingId(null);
                      } else if (e.key === "Escape") {
                        setEditingId(null);
                      }
                    }}
                    onClick={(e) => e.stopPropagation()}
                    autoFocus
                    size="small"
                    sx={{ flex: 1 }}
                  />
                  <Box sx={{ display: "flex", gap: 1 }}>
                    <Button
                      size="small"
                      onClick={(e) => {
                        e.stopPropagation();
                        onEditName?.(asset, editedName);
                        setEditingId(null);
                      }}
                      variant="contained"
                    >
                      Save
                    </Button>
                    <Button
                      size="small"
                      onClick={(e) => {
                        e.stopPropagation();
                        setEditingId(null);
                      }}
                    >
                      Cancel
                    </Button>
                  </Box>
                </Box>
              );
            }

            return (
              <Box sx={{ display: "flex", alignItems: "center", gap: 1, p: 1 }}>
                <TableCellContent variant="primary">
                  {currentName}
                </TableCellContent>
                {onEditName && (
                  <IconButton
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation();
                      setEditingId(asset.InventoryID);
                      setEditedName(currentName);
                    }}
                  >
                    <EditIcon fontSize="small" />
                  </IconButton>
                )}
              </Box>
            );
          },
        };
      }
      return col;
    });
  }, [userColumns, editingId, editedName, onEditName]);

  const table = useReactTable({
    data,
    columns,
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      columnSizing,
      globalFilter,
    },
    enableSorting: true,
    enableFilters: true,
    onSortingChange: onSortingChange,
    onColumnFiltersChange: onColumnFiltersChange,
    onColumnVisibilityChange: setColumnVisibility,
    onColumnSizingChange: setColumnSizing,
    onGlobalFilterChange: setGlobalFilter,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getSortedRowModel: getSortedRowModel(),
    columnResizeMode: "onChange" as ColumnResizeMode,
    filterFns: {
      includesString: (row, columnId, filterValue) => {
        const value = String(row.getValue(columnId) || "").toLowerCase();
        return value.includes(String(filterValue).toLowerCase());
      },
    },
  });

  const { rows } = table.getRowModel();
  const rowVirtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => containerRef.current,
    estimateSize: () => 53,
    overscan: 20,
  });

  const handleRowClick = (row: Row<T>) => {
    if (onRowClick && row.original) {
      onRowClick(row.original);
    }
  };

  return (
    <Box
      sx={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <BaseTableToolbar
        globalFilter={globalFilter}
        onGlobalFilterChange={setGlobalFilter}
        onColumnMenuOpen={(event) => setColumnMenuAnchor(event.currentTarget)}
        activeFilters={columnFilters.map((f) => ({
          columnId: f.id,
          value: f.value as string,
        }))}
        activeSorting={sorting.map((s) => ({ columnId: s.id, desc: s.desc }))}
        onRemoveFilter={(columnId) => {
          onColumnFiltersChange?.(
            columnFilters.filter((f) => f.id !== columnId),
          );
        }}
        onRemoveSort={(columnId) => {
          onSortingChange?.(sorting.filter((s) => s.id !== columnId));
        }}
        searchPlaceholder={searchPlaceholder}
      />

      <ResizableTable
        table={table}
        containerRef={containerRef}
        virtualizer={rowVirtualizer}
        rows={rows}
        onRowClick={(row) => handleRowClick(row)}
        maxHeight="none"
      />
    </Box>
  );
}
