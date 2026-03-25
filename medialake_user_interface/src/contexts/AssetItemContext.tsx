/**
 * AssetItemContext — eliminates prop drilling of asset action handlers
 * and accessor functions through AssetResultsView → AssetGridView → AssetCard.
 *
 * Split into 3 contexts to minimize re-renders:
 * 1. AccessorsContext — stable asset data accessors (rarely change)
 * 2. ActionsContext — event handlers (change when callbacks change)
 * 3. EditingContext — frequently-changing editing/selection state
 */
import React, { createContext, useContext, useMemo } from "react";

// ─── Accessors (stable, rarely change) ───
export interface AssetAccessors<T = any> {
  getAssetId: (asset: T) => string;
  getAssetName: (asset: T) => string;
  getAssetType: (asset: T) => string;
  getAssetThumbnail: (asset: T) => string;
  getAssetProxy?: (asset: T) => string;
  renderCardField: (fieldId: string, asset: T) => React.ReactNode;
}

// ─── Actions (handlers, change when callbacks change) ───
export interface AssetActions<T = any> {
  onAssetClick: (asset: T) => void;
  onDeleteClick: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  onDownloadClick: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  onAddToCollectionClick?: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  showRemoveButton?: boolean;
  onEditClick: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  onEditNameChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onEditNameComplete: (asset: T, save: boolean, value?: string) => void;
  onFavoriteToggle?: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
  onSelectToggle?: (asset: T, event: React.MouseEvent<HTMLElement>) => void;
}

// ─── Editing state (changes frequently) ───
export interface AssetEditingState {
  editingAssetId?: string;
  editedName?: string;
  isRenaming?: boolean;
  renamingAssetId?: string;
  isAssetFavorited?: (assetId: string) => boolean;
  isAssetSelected?: (assetId: string) => boolean;
  isSemantic?: boolean;
  confidenceThreshold?: number;
}

// ─── Combined type for backward compatibility ───
export interface AssetItemActions<T = any>
  extends AssetAccessors<T>,
    AssetActions<T>,
    AssetEditingState {}

// ─── Contexts ───
const AccessorsContext = createContext<AssetAccessors | null>(null);
const ActionsContext = createContext<AssetActions | null>(null);
const EditingContext = createContext<AssetEditingState | null>(null);

export function AssetItemProvider<T>({
  children,
  value,
}: {
  children: React.ReactNode;
  value: AssetItemActions<T>;
}) {
  const accessors = useMemo(
    () => ({
      getAssetId: value.getAssetId,
      getAssetName: value.getAssetName,
      getAssetType: value.getAssetType,
      getAssetThumbnail: value.getAssetThumbnail,
      getAssetProxy: value.getAssetProxy,
      renderCardField: value.renderCardField,
    }),
    [
      value.getAssetId,
      value.getAssetName,
      value.getAssetType,
      value.getAssetThumbnail,
      value.getAssetProxy,
      value.renderCardField,
    ]
  );

  const actions = useMemo(
    () => ({
      onAssetClick: value.onAssetClick,
      onDeleteClick: value.onDeleteClick,
      onDownloadClick: value.onDownloadClick,
      onAddToCollectionClick: value.onAddToCollectionClick,
      showRemoveButton: value.showRemoveButton,
      onEditClick: value.onEditClick,
      onEditNameChange: value.onEditNameChange,
      onEditNameComplete: value.onEditNameComplete,
      onFavoriteToggle: value.onFavoriteToggle,
      onSelectToggle: value.onSelectToggle,
    }),
    [
      value.onAssetClick,
      value.onDeleteClick,
      value.onDownloadClick,
      value.onAddToCollectionClick,
      value.showRemoveButton,
      value.onEditClick,
      value.onEditNameChange,
      value.onEditNameComplete,
      value.onFavoriteToggle,
      value.onSelectToggle,
    ]
  );

  const editing = useMemo(
    () => ({
      editingAssetId: value.editingAssetId,
      editedName: value.editedName,
      isRenaming: value.isRenaming,
      renamingAssetId: value.renamingAssetId,
      isAssetFavorited: value.isAssetFavorited,
      isAssetSelected: value.isAssetSelected,
      isSemantic: value.isSemantic,
      confidenceThreshold: value.confidenceThreshold,
    }),
    [
      value.editingAssetId,
      value.editedName,
      value.isRenaming,
      value.renamingAssetId,
      value.isAssetFavorited,
      value.isAssetSelected,
      value.isSemantic,
      value.confidenceThreshold,
    ]
  );

  return (
    <AccessorsContext.Provider value={accessors}>
      <ActionsContext.Provider value={actions}>
        <EditingContext.Provider value={editing}>{children}</EditingContext.Provider>
      </ActionsContext.Provider>
    </AccessorsContext.Provider>
  );
}

/**
 * Combined hook — backward compatible, returns all values.
 * Memoizes the merged object so consumers don't get a new reference every render.
 * Prefer the granular hooks below for better performance.
 */
export function useAssetItemActions<T = any>(): AssetItemActions<T> {
  const accessors = useContext(AccessorsContext);
  const actions = useContext(ActionsContext);
  const editing = useContext(EditingContext);
  if (!accessors || !actions || !editing) {
    throw new Error("useAssetItemActions must be used within an AssetItemProvider");
  }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  return useMemo(
    () => ({ ...accessors, ...actions, ...editing }) as AssetItemActions<T>,
    [accessors, actions, editing]
  );
}

/** Only re-renders when accessor functions change (rare). */
export function useAssetAccessors<T = any>(): AssetAccessors<T> {
  const ctx = useContext(AccessorsContext);
  if (!ctx) throw new Error("useAssetAccessors must be used within an AssetItemProvider");
  return ctx as AssetAccessors<T>;
}

/** Only re-renders when action handlers change. */
export function useAssetActions<T = any>(): AssetActions<T> {
  const ctx = useContext(ActionsContext);
  if (!ctx) throw new Error("useAssetActions must be used within an AssetItemProvider");
  return ctx as AssetActions<T>;
}

/** Re-renders when editing/selection state changes. */
export function useAssetEditingState(): AssetEditingState {
  const ctx = useContext(EditingContext);
  if (!ctx) throw new Error("useAssetEditingState must be used within an AssetItemProvider");
  return ctx;
}
