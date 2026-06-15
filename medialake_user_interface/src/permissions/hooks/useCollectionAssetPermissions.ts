import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { usePermission } from "./usePermission";

interface CollectionAssetPermissionResult {
  /** Whether the user can add assets to collections */
  canAdd: boolean;
  /** Whether the user can remove assets from collections */
  canRemove: boolean;
  /** Tooltip shown when adding is not permitted */
  addTooltip: string;
  /** Tooltip shown when removing is not permitted */
  removeTooltip: string;
  /** Props spread helper for the "add to collection" control (MUI Button/IconButton) */
  addDisabledProps: {
    disabled: boolean;
    title: string;
  };
  /** Props spread helper for the "remove from collection" control */
  removeDisabledProps: {
    disabled: boolean;
    title: string;
  };
}

/**
 * Centralized permission checks for adding/removing assets to collections.
 *
 * Backward compatibility: the dedicated `collections:add_assets` /
 * `collections:remove_assets` permissions are honored, but a user who still
 * holds the broader `collections:edit` permission retains the ability to add
 * and remove assets. This mirrors the OR-fallback enforced by the backend
 * authorizer so the UI and API stay in sync.
 *
 * Usage:
 * ```tsx
 * const { canAdd, addDisabledProps } = useCollectionAssetPermissions();
 * <IconButton {...addDisabledProps} onClick={handleAdd}>...</IconButton>
 * ```
 */
export function useCollectionAssetPermissions(): CollectionAssetPermissionResult {
  const { can, loading } = usePermission();
  const { t } = useTranslation();

  return useMemo(() => {
    // While loading, default to disabled to prevent unauthorized flashes.
    const canEdit = loading ? false : can("edit", "collection");
    const canAdd = loading ? false : can("add_assets", "collection") || canEdit;
    const canRemove = loading ? false : can("remove_assets", "collection") || canEdit;

    const noPermission = t(
      "permissions.noPermission",
      "You don't have permission to perform this action"
    );

    const addTooltip = canAdd ? "" : noPermission;
    const removeTooltip = canRemove ? "" : noPermission;

    return {
      canAdd,
      canRemove,
      addTooltip,
      removeTooltip,
      addDisabledProps: {
        disabled: !canAdd,
        title: addTooltip,
      },
      removeDisabledProps: {
        disabled: !canRemove,
        title: removeTooltip,
      },
    };
  }, [can, loading, t]);
}
