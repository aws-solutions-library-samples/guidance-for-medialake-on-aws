import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { FacetFilters } from "../types/facetSearch";

// Define the filter modal form state interface
interface FilterModalFormState {
  selectedMediaTypes: string[];
  selectedExtensions: string[];
  minSizeValue: number | "";
  maxSizeValue: number | "";
  sizeUnit: number;
  dateRangeOption: string | null;
  startDate: Date | null;
  endDate: Date | null;
}

// Initial state for the filter modal form
const initialFilterModalState: FilterModalFormState = {
  selectedMediaTypes: [],
  selectedExtensions: [],
  minSizeValue: "",
  maxSizeValue: "",
  sizeUnit: 1024 * 1024, // Default to MB
  dateRangeOption: null,
  startDate: null,
  endDate: null,
};

// File size units for conversion
const FILE_SIZE_UNITS = [
  { value: 1, label: "B" },
  { value: 1024, label: "KB" },
  { value: 1024 * 1024, label: "MB" },
  { value: 1024 * 1024 * 1024, label: "GB" },
];

// Helper function to convert bytes to appropriate unit for display
const convertBytesToDisplayUnit = (bytes: number) => {
  if (bytes >= FILE_SIZE_UNITS[3].value) {
    return {
      value: bytes / FILE_SIZE_UNITS[3].value,
      unit: FILE_SIZE_UNITS[3].value,
    };
  } else if (bytes >= FILE_SIZE_UNITS[2].value) {
    return {
      value: bytes / FILE_SIZE_UNITS[2].value,
      unit: FILE_SIZE_UNITS[2].value,
    };
  } else if (bytes >= FILE_SIZE_UNITS[1].value) {
    return {
      value: bytes / FILE_SIZE_UNITS[1].value,
      unit: FILE_SIZE_UNITS[1].value,
    };
  } else {
    return { value: bytes, unit: FILE_SIZE_UNITS[0].value };
  }
};

// Helper function to check if two dates are the same day
const isSameDay = (date1: Date, date2: Date) => {
  return (
    date1.getFullYear() === date2.getFullYear() &&
    date1.getMonth() === date2.getMonth() &&
    date1.getDate() === date2.getDate()
  );
};

// Helper functions for converting between form state and filters
function convertFiltersToFormState(
  filters: FacetFilters,
): FilterModalFormState {
  // Initialize media types - handle comma-separated list
  const newMediaTypes = filters.type ? filters.type.split(",") : [];

  // Initialize extensions - handle comma-separated list
  // Convert back to lowercase to match UI button values
  const newExtensions = filters.extension
    ? filters.extension.split(",").map((ext) => ext.toLowerCase())
    : [];

  // Initialize file size
  let newMinSizeValue: number | "" = "";
  let newMaxSizeValue: number | "" = "";
  let newSizeUnit = 1024 * 1024; // Default to MB

  if (filters.asset_size_gte !== undefined) {
    // Find appropriate unit for display
    const { value, unit } = convertBytesToDisplayUnit(filters.asset_size_gte);
    newMinSizeValue = value;
    newSizeUnit = unit;
  }

  if (filters.asset_size_lte !== undefined) {
    // Find appropriate unit for display
    const { value, unit } = convertBytesToDisplayUnit(filters.asset_size_lte);
    newMaxSizeValue = value;
    if (filters.asset_size_gte === undefined) {
      newSizeUnit = unit;
    }
  }

  // Initialize date range
  let newDateRangeOption: string | null = null;
  let newStartDate: Date | null = null;
  let newEndDate: Date | null = null;

  if (filters.date_range_option) {
    // If we have a stored date range option, use it
    newDateRangeOption = filters.date_range_option;

    if (filters.ingested_date_gte) {
      newStartDate = new Date(filters.ingested_date_gte);
    }

    if (filters.ingested_date_lte) {
      newEndDate = new Date(filters.ingested_date_lte);
    }
  } else if (filters.ingested_date_gte && filters.ingested_date_lte) {
    // Try to determine the date range option from the dates
    const now = new Date();
    const startDateObj = new Date(filters.ingested_date_gte);
    const endDateObj = new Date(filters.ingested_date_lte);

    const daysDiff = Math.round(
      (now.getTime() - startDateObj.getTime()) / (1000 * 60 * 60 * 24),
    );

    if (daysDiff <= 1 && isSameDay(endDateObj, now)) {
      newDateRangeOption = "24h";
    } else if (daysDiff <= 7 && isSameDay(endDateObj, now)) {
      newDateRangeOption = "7d";
    } else if (daysDiff <= 14 && isSameDay(endDateObj, now)) {
      newDateRangeOption = "14d";
    } else if (daysDiff <= 30 && isSameDay(endDateObj, now)) {
      newDateRangeOption = "30d";
    }

    newStartDate = startDateObj;
    newEndDate = endDateObj;
  }

  return {
    selectedMediaTypes: newMediaTypes,
    selectedExtensions: newExtensions,
    minSizeValue: newMinSizeValue,
    maxSizeValue: newMaxSizeValue,
    sizeUnit: newSizeUnit,
    dateRangeOption: newDateRangeOption,
    startDate: newStartDate,
    endDate: newEndDate,
  };
}

function convertFormStateToFilters(
  formState: FilterModalFormState,
): FacetFilters {
  const filters: FacetFilters = {};

  // Apply media type filters - now supports multiple types
  if (formState.selectedMediaTypes.length > 0) {
    filters.type = formState.selectedMediaTypes.join(",");
  }

  // Apply extension filters - now supports multiple extensions
  if (formState.selectedExtensions.length > 0) {
    // Convert extensions to uppercase before sending to API
    filters.extension = formState.selectedExtensions
      .map((ext) => ext.toUpperCase())
      .join(",");
  }

  // Convert size inputs to bytes for API
  if (formState.minSizeValue !== "") {
    filters.asset_size_gte =
      Number(formState.minSizeValue) * formState.sizeUnit;
  }

  if (formState.maxSizeValue !== "") {
    filters.asset_size_lte =
      Number(formState.maxSizeValue) * formState.sizeUnit;
  }

  // Store the selected date range option in the filters
  if (formState.dateRangeOption !== null) {
    filters.date_range_option = formState.dateRangeOption;
  }

  // Apply date range filters
  if (formState.startDate) {
    filters.ingested_date_gte = formState.startDate.toISOString();
  }

  if (formState.endDate) {
    filters.ingested_date_lte = formState.endDate.toISOString();
  }

  return filters;
}

export interface SearchState {
  // Domain state
  query: string;
  isSemantic: boolean;
  filters: FacetFilters;

  // UI state
  ui: {
    filterModalOpen: boolean;
    filterModalDraft: FilterModalFormState;
    loading: boolean;
    error?: string;
  };

  // Actions
  actions: {
    // Domain actions
    setQuery: (query: string) => void;
    setIsSemantic: (isSemantic: boolean) => void;
    setFilters: (filters: FacetFilters) => void;
    updateFilter: <K extends keyof FacetFilters>(
      key: K,
      value: FacetFilters[K],
    ) => void;
    clearFilters: () => void;

    // UI actions
    openFilterModal: () => void;
    closeFilterModal: () => void;
    updateFilterModalDraft: (draft: Partial<FilterModalFormState>) => void;
    applyFilterModalDraft: () => void;
    resetFilterModalDraft: () => void;
    setLoading: (loading: boolean) => void;
    setError: (error?: string) => void;

    // Computed values
    hasActiveFilters: () => boolean;
    activeFilterCount: () => number;
  };
}

export const useSearchStore = create<SearchState>()(
  persist(
    (set, get) => ({
      // Domain state
      query: "",
      isSemantic: false,
      filters: {},

      // UI state
      ui: {
        filterModalOpen: false,
        filterModalDraft: initialFilterModalState,
        loading: false,
        error: undefined,
      },

      // Actions
      actions: {
        // Domain actions
        setQuery: (query) => set({ query }),

        setIsSemantic: (isSemantic) => set({ isSemantic }),

        setFilters: (filters) => {
          // Only update if different to prevent infinite loops
          const currentFilters = get().filters;
          if (JSON.stringify(currentFilters) !== JSON.stringify(filters)) {
            set({ filters });
          }
        },

        updateFilter: <K extends keyof FacetFilters>(
          key: K,
          value: FacetFilters[K],
        ) => {
          const currentFilters = get().filters;
          const updatedFilters = {
            ...currentFilters,
            [key]: value,
          };

          // Remove undefined values
          Object.keys(updatedFilters).forEach((k) => {
            if (updatedFilters[k as keyof FacetFilters] === undefined) {
              delete updatedFilters[k as keyof FacetFilters];
            }
          });

          // Only update if different
          if (
            JSON.stringify(currentFilters) !== JSON.stringify(updatedFilters)
          ) {
            set({ filters: updatedFilters });
          }
        },

        clearFilters: () =>
          set({
            filters: {},
            ui: {
              ...get().ui,
              filterModalDraft: initialFilterModalState,
            },
          }),

        // UI actions
        openFilterModal: () => {
          // Initialize draft state from current filters when opening
          const currentFilters = get().filters;
          set({
            ui: {
              ...get().ui,
              filterModalOpen: true,
              filterModalDraft: convertFiltersToFormState(currentFilters),
            },
          });
        },

        closeFilterModal: () =>
          set({
            ui: {
              ...get().ui,
              filterModalOpen: false,
            },
          }),

        updateFilterModalDraft: (draft) =>
          set({
            ui: {
              ...get().ui,
              filterModalDraft: {
                ...get().ui.filterModalDraft,
                ...draft,
              },
            },
          }),

        applyFilterModalDraft: () => {
          const draft = get().ui.filterModalDraft;
          const filters = convertFormStateToFilters(draft);
          // Only update if different
          const currentFilters = get().filters;
          if (JSON.stringify(filters) !== JSON.stringify(currentFilters)) {
            set({ filters });
          }
        },

        resetFilterModalDraft: () =>
          set({
            ui: {
              ...get().ui,
              filterModalDraft: initialFilterModalState,
            },
          }),

        setLoading: (loading: boolean) =>
          set({
            ui: {
              ...get().ui,
              loading,
            },
          }),

        setError: (error?: string) =>
          set({
            ui: {
              ...get().ui,
              error,
            },
          }),

        // Computed values
        hasActiveFilters: () => {
          const filters = get().filters;
          return Object.values(filters).filter(Boolean).length > 0;
        },

        activeFilterCount: () => {
          const filters = get().filters;
          return Object.values(filters).filter(Boolean).length;
        },
      },
    }),
    {
      name: "search-store",
      storage: createJSONStorage(() => sessionStorage),
      // Only persist domain state, not UI state
      partialize: (state) => ({
        query: state.query,
        isSemantic: state.isSemantic,
        filters: state.filters,
      }),
    },
  ),
);

// Domain state selectors
export const useSearchQuery = () => useSearchStore((state) => state.query);
export const useSemanticSearch = () =>
  useSearchStore((state) => state.isSemantic);
export const useSearchFilters = () => useSearchStore((state) => state.filters);

// UI state selectors
export const useFilterModalOpen = () =>
  useSearchStore((state) => state.ui.filterModalOpen);
export const useFilterModalDraft = () =>
  useSearchStore((state) => state.ui.filterModalDraft);

// Action selectors
export const useSearchActions = () => useSearchStore((state) => state.actions);
export const useDomainActions = () => {
  const { setQuery, setIsSemantic, setFilters, updateFilter, clearFilters } =
    useSearchStore((state) => state.actions);
  return { setQuery, setIsSemantic, setFilters, updateFilter, clearFilters };
};
export const useUIActions = () => {
  const {
    openFilterModal,
    closeFilterModal,
    updateFilterModalDraft,
    applyFilterModalDraft,
    resetFilterModalDraft,
    setLoading,
    setError,
  } = useSearchStore((state) => state.actions);
  return {
    openFilterModal,
    closeFilterModal,
    updateFilterModalDraft,
    applyFilterModalDraft,
    resetFilterModalDraft,
    setLoading,
    setError,
  };
};
