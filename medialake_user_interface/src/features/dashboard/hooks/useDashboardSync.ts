import { useEffect, useRef, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useGetDashboardLayout,
  useSaveDashboardLayout,
  useResetDashboardLayout,
} from "@/api/hooks/useDashboard";
import { QUERY_KEYS } from "@/api/queryKeys";
import {
  useDashboardStore,
  convertApiLayoutToFrontend,
  convertFrontendLayoutToApi,
  DEFAULT_LAYOUT,
} from "../store/dashboardStore";

const DEBOUNCE_DELAY = 2000; // 2 seconds debounce for auto-save

/**
 * Hook to synchronize dashboard layout between local store and API.
 *
 * This hook:
 * 1. Loads the layout from API on mount
 * 2. Falls back to localStorage if API fails
 * 3. Auto-saves changes to API with debouncing
 * 4. Provides manual save/reset functions
 */
export const useDashboardSync = () => {
  const queryClient = useQueryClient();
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isInitialLoadRef = useRef(true);

  // Store state - use individual selectors for stable references
  const layout = useDashboardStore((state) => state.layout);
  const hasPendingChanges = useDashboardStore((state) => state.hasPendingChanges);

  // Store actions - use individual selectors for stable references (these are stable function references)
  const setLayout = useDashboardStore((state) => state.setLayout);
  const setIsSyncing = useDashboardStore((state) => state.setIsSyncing);
  const setLastSyncError = useDashboardStore((state) => state.setLastSyncError);
  const setHasPendingChanges = useDashboardStore((state) => state.setHasPendingChanges);

  // API hooks
  const {
    data: apiLayout,
    isLoading: isLoadingLayout,
    error: loadError,
    isSuccess: isLoadSuccess,
  } = useGetDashboardLayout();

  const saveLayoutMutation = useSaveDashboardLayout();
  const resetLayoutMutation = useResetDashboardLayout();

  // Load layout from API on mount
  useEffect(() => {
    if (isLoadSuccess && apiLayout && isInitialLoadRef.current) {
      isInitialLoadRef.current = false;
      const frontendLayout = convertApiLayoutToFrontend(apiLayout);
      setLayout(frontendLayout);
      setHasPendingChanges(false);
      setLastSyncError(null);
    }
  }, [isLoadSuccess, apiLayout, setLayout, setHasPendingChanges, setLastSyncError]);

  // Handle load error - keep using localStorage data
  useEffect(() => {
    if (loadError && isInitialLoadRef.current) {
      isInitialLoadRef.current = false;
      console.warn("Failed to load dashboard layout from API, using local storage:", loadError);
      setLastSyncError("Failed to load layout from server");
    }
  }, [loadError, setLastSyncError]);

  // Debounced auto-save when layout changes
  useEffect(() => {
    // Skip if initial load or no pending changes
    if (isInitialLoadRef.current || !hasPendingChanges) {
      return;
    }

    // Clear existing timeout
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    // Set new timeout for debounced save
    saveTimeoutRef.current = setTimeout(() => {
      const apiPayload = convertFrontendLayoutToApi(layout);
      setIsSyncing(true);

      saveLayoutMutation.mutate(apiPayload, {
        onSuccess: () => {
          setHasPendingChanges(false);
          setLastSyncError(null);
          setIsSyncing(false);
        },
        onError: (error) => {
          console.error("Auto-save failed:", error);
          setLastSyncError("Failed to save layout");
          setIsSyncing(false);
        },
      });
    }, DEBOUNCE_DELAY);

    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, [
    layout,
    hasPendingChanges,
    saveLayoutMutation,
    setIsSyncing,
    setHasPendingChanges,
    setLastSyncError,
  ]);

  // Manual save function (immediate, no debounce)
  const saveNow = useCallback(() => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    const apiPayload = convertFrontendLayoutToApi(layout);
    setIsSyncing(true);

    return saveLayoutMutation
      .mutateAsync(apiPayload)
      .then(() => {
        setHasPendingChanges(false);
        setLastSyncError(null);
        setIsSyncing(false);
      })
      .catch((error) => {
        setLastSyncError("Failed to save layout");
        setIsSyncing(false);
        throw error;
      });
  }, [layout, saveLayoutMutation, setIsSyncing, setHasPendingChanges, setLastSyncError]);

  // Reset to default layout via API
  const resetLayout = useCallback(() => {
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    setIsSyncing(true);

    return resetLayoutMutation
      .mutateAsync()
      .then((apiLayout) => {
        const frontendLayout = convertApiLayoutToFrontend(apiLayout);
        setLayout(frontendLayout);
        setHasPendingChanges(false);
        setLastSyncError(null);
        setIsSyncing(false);
      })
      .catch((error) => {
        // Fallback to local default if API fails
        console.warn("API reset failed, using local default:", error);
        setLayout(DEFAULT_LAYOUT);
        setHasPendingChanges(true); // Mark for sync
        setLastSyncError("Reset to local default (server unavailable)");
        setIsSyncing(false);
      });
  }, [resetLayoutMutation, setLayout, setIsSyncing, setHasPendingChanges, setLastSyncError]);

  // Refresh layout from API
  const refreshLayout = useCallback(() => {
    return queryClient.invalidateQueries({ queryKey: QUERY_KEYS.DASHBOARD.layout() });
  }, [queryClient]);

  return {
    isLoading: isLoadingLayout,
    isSaving: saveLayoutMutation.isPending,
    hasPendingChanges,
    saveNow,
    resetLayout,
    refreshLayout,
    error: loadError,
  };
};

export default useDashboardSync;
