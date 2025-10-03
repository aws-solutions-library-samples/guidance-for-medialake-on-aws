import { useState, useCallback } from "react";
import { type SortingState } from "@tanstack/react-table";
import { type AssetTableColumn } from "@/types/shared/assetComponents";

interface ViewPreferencesOptions {
  initialViewMode?: "card" | "table";
  initialCardSize?: "small" | "medium" | "large";
  initialAspectRatio?: "vertical" | "square" | "horizontal";
  initialThumbnailScale?: "fit" | "fill";
  initialShowMetadata?: boolean;
  initialGroupByType?: boolean;
  initialSorting?: SortingState;
}

export function useViewPreferences<T>({
  initialViewMode = "card",
  initialCardSize = "medium",
  initialAspectRatio = "square",
  initialThumbnailScale = "fit",
  initialShowMetadata = true,
  initialGroupByType = false,
  initialSorting = [],
}: ViewPreferencesOptions = {}) {
  // View mode state
  const [viewMode, setViewMode] = useState<"card" | "table">(initialViewMode);
  const [cardSize, setCardSize] = useState<"small" | "medium" | "large">(
    initialCardSize,
  );
  const [aspectRatio, setAspectRatio] = useState<
    "vertical" | "square" | "horizontal"
  >(initialAspectRatio);
  const [thumbnailScale, setThumbnailScale] = useState<"fit" | "fill">(
    initialThumbnailScale,
  );
  const [showMetadata, setShowMetadata] = useState(initialShowMetadata);
  const [groupByType, setGroupByType] = useState(initialGroupByType);
  const [sorting, setSorting] = useState<SortingState>(initialSorting);

  // Card fields and columns state
  const [cardFields, setCardFields] = useState([
    { id: "name", label: "Object Name", visible: true },
    { id: "type", label: "Type", visible: true },
    { id: "format", label: "Format", visible: true },
    { id: "size", label: "File Size", visible: true },
    { id: "fullPath", label: "Full Path", visible: true },
    { id: "createdAt", label: "Date Created", visible: true },
  ]);

  // Handle view mode change
  const handleViewModeChange = useCallback(
    (_: React.MouseEvent<HTMLElement>, newMode: "card" | "table" | null) => {
      if (newMode) setViewMode(newMode);
    },
    [],
  );

  // Handle card size change
  const handleCardSizeChange = useCallback(
    (size: "small" | "medium" | "large") => {
      setCardSize(size);
    },
    [],
  );

  // Handle aspect ratio change
  const handleAspectRatioChange = useCallback(
    (ratio: "vertical" | "square" | "horizontal") => {
      setAspectRatio(ratio);
    },
    [],
  );

  // Handle thumbnail scale change
  const handleThumbnailScaleChange = useCallback((scale: "fit" | "fill") => {
    setThumbnailScale(scale);
  }, []);

  // Handle show metadata change
  const handleShowMetadataChange = useCallback((show: boolean) => {
    setShowMetadata(show);
  }, []);

  // Handle group by type change
  const handleGroupByTypeChange = useCallback((checked: boolean) => {
    setGroupByType(checked);
  }, []);

  // Handle sort change
  const handleSortChange = useCallback((newSorting: SortingState) => {
    setSorting(newSorting);
  }, []);

  // Handle card field toggle
  const handleCardFieldToggle = useCallback((fieldId: string) => {
    setCardFields((prev) =>
      prev.map((field) =>
        field.id === fieldId ? { ...field, visible: !field.visible } : field,
      ),
    );
  }, []);

  // Handle column toggle
  const handleColumnToggle = useCallback((columnId: string) => {
    // This function will be implemented in the component that uses this hook
    // since columns are typically defined in the component
  }, []);

  return {
    // State
    viewMode,
    cardSize,
    aspectRatio,
    thumbnailScale,
    showMetadata,
    groupByType,
    sorting,
    cardFields,

    // Handlers
    handleViewModeChange,
    handleCardSizeChange,
    handleAspectRatioChange,
    handleThumbnailScaleChange,
    handleShowMetadataChange,
    handleGroupByTypeChange,
    handleSortChange,
    handleCardFieldToggle,
    handleColumnToggle,

    // Setters (for direct state updates if needed)
    setViewMode,
    setCardSize,
    setAspectRatio,
    setThumbnailScale,
    setShowMetadata,
    setGroupByType,
    setSorting,
    setCardFields,
  };
}
