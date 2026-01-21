import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSnackbar } from "notistack";
import { useTranslation } from "react-i18next";
import { apiClient } from "../apiClient";
import { API_ENDPOINTS } from "../endpoints";
import { QUERY_KEYS } from "../queryKeys";

// Types matching the backend API
export interface WidgetInstance {
  id: string;
  type: "favorites" | "my-collections" | "recent-assets";
  config?: Record<string, unknown>;
}

export interface LayoutItem {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
  maxW?: number;
  maxH?: number;
}

export interface DashboardLayout {
  layoutVersion: number;
  widgets: WidgetInstance[];
  layouts: {
    lg: LayoutItem[];
    md: LayoutItem[];
    sm: LayoutItem[];
  };
  updatedAt: string;
}

export interface SaveLayoutRequest {
  widgets: WidgetInstance[];
  layouts: {
    lg: LayoutItem[];
    md: LayoutItem[];
    sm: LayoutItem[];
  };
}

export interface SaveLayoutResponse {
  layoutVersion: number;
  updatedAt: string;
}

export interface PresetSummary {
  presetId: string;
  name: string;
  description?: string;
  widgetCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface PresetResponse {
  presetId: string;
  name: string;
  description?: string;
  widgets: WidgetInstance[];
  layouts: {
    lg: LayoutItem[];
    md: LayoutItem[];
    sm: LayoutItem[];
  };
  createdAt: string;
  updatedAt: string;
}

export interface CreatePresetRequest {
  name: string;
  description?: string;
}

export interface UpdatePresetRequest {
  name?: string;
  description?: string;
  widgets?: WidgetInstance[];
  layouts?: {
    lg: LayoutItem[];
    md: LayoutItem[];
    sm: LayoutItem[];
  };
}

// API Response wrapper types
interface ApiResponse<T> {
  success: boolean;
  data: T;
  meta?: {
    timestamp: string;
    version: string;
    request_id?: string;
  };
}

interface ApiErrorResponse {
  success: boolean;
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

/**
 * Hook to fetch user's dashboard layout
 */
export const useGetDashboardLayout = () => {
  return useQuery<DashboardLayout, Error>({
    queryKey: QUERY_KEYS.DASHBOARD.layout(),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<DashboardLayout>>(
        API_ENDPOINTS.DASHBOARD.LAYOUT
      );
      return data.data;
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
    gcTime: 1000 * 60 * 30, // 30 minutes
    refetchOnWindowFocus: false,
  });
};

/**
 * Hook to save dashboard layout
 */
export const useSaveDashboardLayout = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();
  const { t } = useTranslation();

  return useMutation<SaveLayoutResponse, Error, SaveLayoutRequest>({
    mutationFn: async (layoutData) => {
      const { data } = await apiClient.put<ApiResponse<SaveLayoutResponse>>(
        API_ENDPOINTS.DASHBOARD.LAYOUT,
        layoutData
      );
      return data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.DASHBOARD.layout() });
    },
    onError: (error) => {
      enqueueSnackbar(t("dashboard.errors.saveFailed", "Failed to save layout"), {
        variant: "error",
        autoHideDuration: 5000,
      });
      console.error("Save layout error:", error);
    },
  });
};

/**
 * Hook to reset dashboard layout to default
 */
export const useResetDashboardLayout = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();
  const { t } = useTranslation();

  return useMutation<DashboardLayout, Error, void>({
    mutationFn: async () => {
      const { data } = await apiClient.post<ApiResponse<DashboardLayout>>(
        API_ENDPOINTS.DASHBOARD.LAYOUT_RESET
      );
      return data.data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(QUERY_KEYS.DASHBOARD.layout(), data);
      enqueueSnackbar(t("dashboard.messages.resetSuccess", "Layout reset to default"), {
        variant: "success",
        autoHideDuration: 3000,
      });
    },
    onError: (error) => {
      enqueueSnackbar(t("dashboard.errors.resetFailed", "Failed to reset layout"), {
        variant: "error",
        autoHideDuration: 5000,
      });
      console.error("Reset layout error:", error);
    },
  });
};

/**
 * Hook to fetch user's presets
 */
export const useGetDashboardPresets = () => {
  return useQuery<PresetSummary[], Error>({
    queryKey: QUERY_KEYS.DASHBOARD.presets(),
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<PresetSummary[]>>(
        API_ENDPOINTS.DASHBOARD.PRESETS
      );
      return data.data;
    },
    staleTime: 1000 * 60 * 5, // 5 minutes
  });
};

/**
 * Hook to fetch a specific preset
 */
export const useGetDashboardPreset = (presetId: string, enabled = true) => {
  return useQuery<PresetResponse, Error>({
    queryKey: QUERY_KEYS.DASHBOARD.preset(presetId),
    enabled: enabled && !!presetId,
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<PresetResponse>>(
        API_ENDPOINTS.DASHBOARD.PRESET(presetId)
      );
      return data.data;
    },
  });
};

/**
 * Hook to create a new preset
 */
export const useCreateDashboardPreset = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();
  const { t } = useTranslation();

  return useMutation<PresetResponse, Error, CreatePresetRequest>({
    mutationFn: async (presetData) => {
      const { data } = await apiClient.post<ApiResponse<PresetResponse>>(
        API_ENDPOINTS.DASHBOARD.PRESETS,
        presetData
      );
      return data.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.DASHBOARD.presets() });
      enqueueSnackbar(t("dashboard.messages.presetCreated", "Preset saved successfully"), {
        variant: "success",
        autoHideDuration: 3000,
      });
    },
    onError: (error: any) => {
      const errorCode = error?.response?.data?.error?.code;
      if (errorCode === "MAX_PRESETS_EXCEEDED") {
        enqueueSnackbar(t("dashboard.errors.maxPresetsExceeded", "Maximum of 5 presets allowed"), {
          variant: "warning",
          autoHideDuration: 5000,
        });
      } else {
        enqueueSnackbar(t("dashboard.errors.presetCreateFailed", "Failed to create preset"), {
          variant: "error",
          autoHideDuration: 5000,
        });
      }
      console.error("Create preset error:", error);
    },
  });
};

/**
 * Hook to update a preset
 */
export const useUpdateDashboardPreset = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();
  const { t } = useTranslation();

  return useMutation<PresetResponse, Error, { presetId: string; data: UpdatePresetRequest }>({
    mutationFn: async ({ presetId, data: presetData }) => {
      const { data } = await apiClient.put<ApiResponse<PresetResponse>>(
        API_ENDPOINTS.DASHBOARD.PRESET(presetId),
        presetData
      );
      return data.data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.DASHBOARD.presets() });
      queryClient.invalidateQueries({
        queryKey: QUERY_KEYS.DASHBOARD.preset(variables.presetId),
      });
      enqueueSnackbar(t("dashboard.messages.presetUpdated", "Preset updated"), {
        variant: "success",
        autoHideDuration: 3000,
      });
    },
    onError: (error) => {
      enqueueSnackbar(t("dashboard.errors.presetUpdateFailed", "Failed to update preset"), {
        variant: "error",
        autoHideDuration: 5000,
      });
      console.error("Update preset error:", error);
    },
  });
};

/**
 * Hook to delete a preset
 */
export const useDeleteDashboardPreset = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();
  const { t } = useTranslation();

  return useMutation<void, Error, string>({
    mutationFn: async (presetId) => {
      await apiClient.delete(API_ENDPOINTS.DASHBOARD.PRESET(presetId));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.DASHBOARD.presets() });
      enqueueSnackbar(t("dashboard.messages.presetDeleted", "Preset deleted"), {
        variant: "success",
        autoHideDuration: 3000,
      });
    },
    onError: (error) => {
      enqueueSnackbar(t("dashboard.errors.presetDeleteFailed", "Failed to delete preset"), {
        variant: "error",
        autoHideDuration: 5000,
      });
      console.error("Delete preset error:", error);
    },
  });
};

/**
 * Hook to apply a preset as the active layout
 */
export const useApplyDashboardPreset = () => {
  const queryClient = useQueryClient();
  const { enqueueSnackbar } = useSnackbar();
  const { t } = useTranslation();

  return useMutation<DashboardLayout, Error, string>({
    mutationFn: async (presetId) => {
      const { data } = await apiClient.post<ApiResponse<DashboardLayout>>(
        API_ENDPOINTS.DASHBOARD.PRESET_APPLY(presetId)
      );
      return data.data;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(QUERY_KEYS.DASHBOARD.layout(), data);
      enqueueSnackbar(t("dashboard.messages.presetApplied", "Preset applied"), {
        variant: "success",
        autoHideDuration: 3000,
      });
    },
    onError: (error) => {
      enqueueSnackbar(t("dashboard.errors.presetApplyFailed", "Failed to apply preset"), {
        variant: "error",
        autoHideDuration: 5000,
      });
      console.error("Apply preset error:", error);
    },
  });
};
