import { useState } from "react";
import { type SortingState } from "@tanstack/react-table";
import { type AssetBase } from "../types/search/searchResults";
import {
  type AssetField,
  type AssetTableColumn,
} from "../types/shared/assetComponents";

interface UseAssetResultsProps<T extends AssetBase> {
  assets: T[];
  searchMetadata: {
    totalResults: number;
    page: number;
    pageSize: number;
  };
  onPageChange: (page: number) => void;
  defaultCardFields: AssetField[];
  defaultColumns: AssetTableColumn<T>[];
  defaultSorting?: SortingState;
}

interface UseAssetResultsReturn<T extends AssetBase> {
  viewMode: "card" | "table";
  sorting: SortingState;
  setSorting: (sorting: SortingState) => void;
  page: number;
  cardFields: AssetField[];
  columns: AssetTableColumn<T>[];
  failedAssets: Set<string>;
  handleViewModeChange: (
    event: React.MouseEvent<HTMLElement>,
    newMode: "card" | "table" | null,
  ) => void;
  handleRequestSort: (columnId: string) => void;
  handlePageChange: (event: React.ChangeEvent<unknown>, value: number) => void;
  handleCardFieldToggle: (fieldId: string) => void;
  handleColumnToggle: (columnId: string) => void;
  handleAssetError: (
    event: React.SyntheticEvent<HTMLImageElement, Event>,
  ) => void;
}

export function useAssetResults<T extends AssetBase>({
  assets,
  searchMetadata,
  onPageChange,
  defaultCardFields,
  defaultColumns,
  defaultSorting = [{ id: "createDate", desc: true }],
}: UseAssetResultsProps<T>): UseAssetResultsReturn<T> {
  const [viewMode, setViewMode] = useState<"card" | "table">("card");
  const [sorting, setSorting] = useState<SortingState>(defaultSorting);
  const [page, setPage] = useState(searchMetadata.page);
  const [cardFields, setCardFields] = useState(defaultCardFields);
  const [columns, setColumns] = useState(defaultColumns);
  const [failedAssets, setFailedAssets] = useState<Set<string>>(new Set());

  const handleViewModeChange = (
    event: React.MouseEvent<HTMLElement>,
    newMode: "card" | "table" | null,
  ) => {
    if (newMode !== null) {
      setViewMode(newMode);
      setPage(1);
    }
  };

  const handleRequestSort = (columnId: string) => {
    const currentSort = sorting[0];
    setSorting([
      {
        id: columnId,
        desc: currentSort?.id === columnId ? !currentSort.desc : false,
      },
    ]);
    setPage(1);
  };

  const handlePageChange = (
    event: React.ChangeEvent<unknown>,
    value: number,
  ) => {
    setPage(value);
    onPageChange(value);
  };

  const handleCardFieldToggle = (fieldId: string) => {
    setCardFields(
      cardFields.map((field) =>
        field.id === fieldId ? { ...field, visible: !field.visible } : field,
      ),
    );
  };

  const handleColumnToggle = (columnId: string) => {
    setColumns(
      columns.map((col) =>
        col.id === columnId ? { ...col, visible: !col.visible } : col,
      ),
    );
  };

  const handleAssetError = (
    event: React.SyntheticEvent<HTMLImageElement, Event>,
  ) => {
    const img = event.target as HTMLImageElement;
    const assetId =
      img.getAttribute("data-image-id") ||
      img.getAttribute("data-video-id") ||
      img.getAttribute("data-audio-id");
    if (assetId) {
      setFailedAssets((prev) => new Set([...prev, assetId]));
    }
  };

  return {
    viewMode,
    sorting,
    setSorting,
    page,
    cardFields,
    columns,
    failedAssets,
    handleViewModeChange,
    handleRequestSort,
    handlePageChange,
    handleCardFieldToggle,
    handleColumnToggle,
    handleAssetError,
  };
}
