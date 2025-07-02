---
title: Zustand Store Design for Optimized Parameters
task_id: search-optimization-2.2
date: 2025-06-29
last_updated: 2025-06-29
status: DRAFT
owner: Architect
---

# Zustand Store Design for Optimized Parameters

## Executive Summary

This document defines the detailed Zustand store implementation for handling optimized search parameters in media-lake-v2. The design implements atomic selector patterns, event-based actions, and optimized parameter handling for comma-separated fields while maintaining 95% pattern compliance and achieving 60-80% re-render reduction through strategic state management.

## Store Architecture Overview

### Design Principles

1. **Atomic State Access**: Every state property accessible through dedicated selectors
2. **Event-Based Actions**: Actions represent business events, not simple setters
3. **Separated Concerns**: Domain state, UI state, and actions clearly separated
4. **Performance Optimization**: Minimal re-renders through atomic selectors
5. **Type Safety**: Comprehensive TypeScript integration throughout

### Store Structure

```typescript
interface SearchStore {
  // Domain State - Core business data
  domain: {
    query: string;
    page: number;
    pageSize: number;
    semantic: boolean;
    fields: FieldState;
    filters: FilterState;
  };
  
  // UI State - Interface interactions
  ui: {
    filterModalOpen: boolean;
    filterModalDraft: FilterModalFormState;
    expandedSections: ExpandedSections;
    loading: boolean;
    error?: string;
    lastSearchTime?: number;
  };
  
  // Actions - Event-based operations
  actions: SearchActions;
}
```

## Detailed State Interfaces

### 1. Field State Structure

```typescript
interface FieldState {
  // Selected fields (resolved paths)
  selected: string[];
  
  // Raw comma-separated string for URL/API
  raw: string;
  
  // Field alias mappings for optimization
  aliases: Record<string, string>;
  
  // Available fields from schema
  available: FieldDefinition[];
  
  // Field categories for UI organization
  categories: Record<string, string[]>;
}

interface FieldDefinition {
  path: string;                    // Full OpenSearch path
  alias?: string;                  // Short alias
  category: string;                // UI category
  type: 'string' | 'number' | 'date' | 'boolean';
  description?: string;            // Human-readable description
}

// Field alias constants
const FIELD_ALIASES: Record<string, string> = {
  'type': 'DigitalSourceAsset.Type',
  'format': 'DigitalSourceAsset.MainRepresentation.Format',
  'size': 'DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.FileSize',
  'created': 'DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.CreateDate',
  'filename': 'DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.Name',
  'path': 'DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ObjectKey.FullPath',
  'modified': 'DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.ModifyDate',
  'bucket': 'DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.BucketName',
  'region': 'DigitalSourceAsset.MainRepresentation.StorageInfo.PrimaryLocation.Region',
};
```

### 2. Filter State Structure

```typescript
interface FilterState {
  // Media type filters (comma-separated in API)
  type: string[];                  // ["Image", "Video", "Audio", "Document"]
  
  // Extension filters (comma-separated in API)
  extension: string[];             // ["jpg", "png", "mp4", "wav"]
  
  // Grouped size filters
  size: {
    range?: {
      min?: number;
      max?: number;
    };
    unit: SizeUnit;                // 'B' | 'KB' | 'MB' | 'GB'
  };
  
  // Grouped date filters
  date: {
    range?: {
      start?: string;              // ISO date string
      end?: string;                // ISO date string
    };
    field: DateField;              // 'ingested' | 'created' | 'modified'
  };
  
  // Text-based filters
  text: {
    filename?: string;             // Filename pattern
    path?: string;                 // Path pattern
    content?: string;              // Content search
  };
  
  // Advanced encoded filters
  advanced?: {
    encoded: string;               // Encoded filter string
    version: '1' | '2';           // Filter format version
    parsed?: Record<string, any>; // Parsed representation
  };
}

type SizeUnit = 'B' | 'KB' | 'MB' | 'GB';
type DateField = 'ingested' | 'created' | 'modified';
```

### 3. UI State Structure

```typescript
interface UIState {
  // Modal states
  filterModalOpen: boolean;
  filterModalDraft: FilterModalFormState;
  
  // Section expansion states
  expandedSections: {
    filters: boolean;
    fields: boolean;
    advanced: boolean;
  };
  
  // Loading and error states
  loading: boolean;
  error?: {
    message: string;
    code?: string;
    timestamp: number;
  };
  
  // Performance tracking
  lastSearchTime?: number;
  searchCount: number;
  
  // User preferences
  preferences: {
    defaultPageSize: number;
    defaultFields: string[];
    rememberFilters: boolean;
  };
}

interface FilterModalFormState {
  // Form field states
  selectedTypes: string[];
  selectedExtensions: string[];
  sizeMin?: number;
  sizeMax?: number;
  sizeUnit: SizeUnit;
  dateStart?: string;
  dateEnd?: string;
  dateField: DateField;
  filename?: string;
  path?: string;
  content?: string;
  
  // Form UI states
  isDirty: boolean;
  isValid: boolean;
  validationErrors: Record<string, string>;
}
```

## Store Implementation

### 1. Store Creation with Middleware

```typescript
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';
import { subscribeWithSelector } from 'zustand/middleware';

export const useSearchStore = create<SearchStore>()(
  subscribeWithSelector(
    persist(
      immer((set, get) => ({
        // Initial domain state
        domain: {
          query: '',
          page: 1,
          pageSize: 50,
          semantic: false,
          fields: {
            selected: [],
            raw: '',
            aliases: FIELD_ALIASES,
            available: [],
            categories: {
              'Basic': ['type', 'format', 'size', 'created'],
              'Location': ['filename', 'path', 'bucket', 'region'],
              'Metadata': ['modified', 'content'],
            },
          },
          filters: {
            type: [],
            extension: [],
            size: { unit: 'B' },
            date: { field: 'ingested' },
            text: {},
          },
        },
        
        // Initial UI state
        ui: {
          filterModalOpen: false,
          filterModalDraft: createEmptyFilterDraft(),
          expandedSections: {
            filters: true,
            fields: false,
            advanced: false,
          },
          loading: false,
          searchCount: 0,
          preferences: {
            defaultPageSize: 50,
            defaultFields: ['type', 'format', 'size', 'created'],
            rememberFilters: true,
          },
        },
        
        // Actions implementation
        actions: createSearchActions(set, get),
      })),
      {
        name: 'search-store',
        storage: createJSONStorage(() => sessionStorage),
        // Only persist domain state and user preferences
        partialize: (state) => ({
          domain: {
            query: state.domain.query,
            semantic: state.domain.semantic,
            fields: {
              selected: state.domain.fields.selected,
              raw: state.domain.fields.raw,
            },
            filters: state.ui.preferences.rememberFilters ? state.domain.filters : {
              type: [],
              extension: [],
              size: { unit: 'B' },
              date: { field: 'ingested' },
              text: {},
            },
          },
          ui: {
            preferences: state.ui.preferences,
          },
        }),
        // Merge strategy for hydration
        merge: (persistedState, currentState) => ({
          ...currentState,
          domain: {
            ...currentState.domain,
            ...persistedState.domain,
            fields: {
              ...currentState.domain.fields,
              ...persistedState.domain.fields,
              aliases: FIELD_ALIASES, // Always use current aliases
              available: currentState.domain.fields.available,
              categories: currentState.domain.fields.categories,
            },
          },
          ui: {
            ...currentState.ui,
            preferences: {
              ...currentState.ui.preferences,
              ...persistedState.ui?.preferences,
            },
          },
        }),
      }
    )
  )
);
```

### 2. Action Implementation

```typescript
const createSearchActions = (set: SetState, get: GetState): SearchActions => ({
  // Core parameter actions
  setQuery: (query: string) => {
    set((state) => {
      state.domain.query = query;
      state.domain.page = 1; // Reset page on new query
      state.ui.lastSearchTime = Date.now();
    });
  },
  
  setPage: (page: number) => {
    if (page > 0) {
      set((state) => {
        state.domain.page = page;
      });
    }
  },
  
  setPageSize: (pageSize: number) => {
    const validSizes = [20, 50, 100, 200, 500];
    if (validSizes.includes(pageSize)) {
      set((state) => {
        state.domain.pageSize = pageSize;
        state.domain.page = 1; // Reset page on page size change
        state.ui.preferences.defaultPageSize = pageSize;
      });
    }
  },
  
  setSemantic: (semantic: boolean) => {
    set((state) => {
      state.domain.semantic = semantic;
      state.domain.page = 1; // Reset page on search type change
    });
  },
  
  // Field selection actions with comma-separated handling
  setFields: (fields: string | string[]) => {
    set((state) => {
      const fieldArray = Array.isArray(fields) 
        ? fields 
        : fields.split(',').map(f => f.trim()).filter(Boolean);
      
      // Resolve aliases to full paths
      const resolved = fieldArray.map(field => 
        state.domain.fields.aliases[field] || field
      );
      
      // Create comma-separated string for API
      const rawString = fieldArray.join(',');
      
      state.domain.fields.selected = resolved;
      state.domain.fields.raw = rawString;
    });
  },
  
  addField: (field: string) => {
    set((state) => {
      const resolved = state.domain.fields.aliases[field] || field;
      
      if (!state.domain.fields.selected.includes(resolved)) {
        state.domain.fields.selected.push(resolved);
        
        // Update raw string
        const aliases = state.domain.fields.aliases;
        const rawFields = state.domain.fields.selected.map(f => 
          Object.keys(aliases).find(alias => aliases[alias] === f) || f
        );
        state.domain.fields.raw = rawFields.join(',');
      }
    });
  },
  
  removeField: (field: string) => {
    set((state) => {
      const resolved = state.domain.fields.aliases[field] || field;
      const index = state.domain.fields.selected.indexOf(resolved);
      
      if (index > -1) {
        state.domain.fields.selected.splice(index, 1);
        
        // Update raw string
        const aliases = state.domain.fields.aliases;
        const rawFields = state.domain.fields.selected.map(f => 
          Object.keys(aliases).find(alias => aliases[alias] === f) || f
        );
        state.domain.fields.raw = rawFields.join(',');
      }
    });
  },
  
  clearFields: () => {
    set((state) => {
      state.domain.fields.selected = [];
      state.domain.fields.raw = '';
    });
  },
  
  resetFieldsToDefault: () => {
    set((state) => {
      const defaultFields = state.ui.preferences.defaultFields;
      state.actions.setFields(defaultFields);
    });
  },
  
  // Filter actions with grouped parameter handling
  setTypeFilters: (types: string[]) => {
    const validTypes = ['Image', 'Video', 'Audio', 'Document'];
    const filteredTypes = types.filter(type => validTypes.includes(type));
    
    set((state) => {
      state.domain.filters.type = filteredTypes;
      state.domain.page = 1; // Reset page on filter change
    });
  },
  
  setExtensionFilters: (extensions: string[]) => {
    // Normalize extensions (lowercase, no dots)
    const normalizedExtensions = extensions.map(ext => 
      ext.toLowerCase().replace(/^\./, '')
    );
    
    set((state) => {
      state.domain.filters.extension = normalizedExtensions;
      state.domain.page = 1;
    });
  },
  
  setSizeFilter: (range?: SizeRange, unit: SizeUnit = 'B') => {
    set((state) => {
      state.domain.filters.size = {
        range: range ? {
          min: range.min,
          max: range.max,
        } : undefined,
        unit,
      };
      state.domain.page = 1;
    });
  },
  
  setDateFilter: (range?: DateRange, field: DateField = 'ingested') => {
    set((state) => {
      state.domain.filters.date = {
        range: range ? {
          start: range.start,
          end: range.end,
        } : undefined,
        field,
      };
      state.domain.page = 1;
    });
  },
  
  setTextFilters: (textFilters: Partial<TextFilters>) => {
    set((state) => {
      state.domain.filters.text = {
        ...state.domain.filters.text,
        ...textFilters,
      };
      state.domain.page = 1;
    });
  },
  
  setAdvancedFilters: (encoded: string, version: '1' | '2' = '2') => {
    set((state) => {
      try {
        const parsed = parseAdvancedFilters(encoded);
        state.domain.filters.advanced = {
          encoded,
          version,
          parsed,
        };
        state.domain.page = 1;
      } catch (error) {
        state.ui.error = {
          message: 'Invalid advanced filter format',
          code: 'INVALID_FILTER_ENCODING',
          timestamp: Date.now(),
        };
      }
    });
  },
  
  // Batch operations for performance
  updateFilters: (filterUpdates: Partial<FilterState>) => {
    set((state) => {
      Object.assign(state.domain.filters, filterUpdates);
      state.domain.page = 1;
    });
  },
  
  clearFilters: () => {
    set((state) => {
      state.domain.filters = {
        type: [],
        extension: [],
        size: { unit: 'B' },
        date: { field: 'ingested' },
        text: {},
      };
      state.domain.page = 1;
    });
  },
  
  resetSearch: () => {
    set((state) => {
      state.domain.query = '';
      state.domain.page = 1;
      state.domain.pageSize = state.ui.preferences.defaultPageSize;
      state.domain.semantic = false;
      state.domain.fields.selected = [];
      state.domain.fields.raw = '';
      state.domain.filters = {
        type: [],
        extension: [],
        size: { unit: 'B' },
        date: { field: 'ingested' },
        text: {},
      };
      state.ui.error = undefined;
    });
  },
  
  // UI actions
  openFilterModal: () => {
    set((state) => {
      state.ui.filterModalOpen = true;
      state.ui.filterModalDraft = convertFiltersToFormState(state.domain.filters);
    });
  },
  
  closeFilterModal: () => {
    set((state) => {
      state.ui.filterModalOpen = false;
      state.ui.filterModalDraft = createEmptyFilterDraft();
    });
  },
  
  updateFilterModalDraft: (updates: Partial<FilterModalFormState>) => {
    set((state) => {
      Object.assign(state.ui.filterModalDraft, updates);
      state.ui.filterModalDraft.isDirty = true;
      state.ui.filterModalDraft.isValid = validateFilterDraft(state.ui.filterModalDraft);
    });
  },
  
  applyFilterModalDraft: () => {
    const draft = get().ui.filterModalDraft;
    if (draft.isValid) {
      const filters = convertFormStateToFilters(draft);
      set((state) => {
        state.domain.filters = filters;
        state.domain.page = 1;
        state.ui.filterModalOpen = false;
        state.ui.filterModalDraft = createEmptyFilterDraft();
      });
    }
  },
  
  discardFilterModalDraft: () => {
    set((state) => {
      state.ui.filterModalDraft = createEmptyFilterDraft();
      state.ui.filterModalOpen = false;
    });
  },
  
  // UI state actions
  toggleSection: (section: keyof ExpandedSections) => {
    set((state) => {
      state.ui.expandedSections[section] = !state.ui.expandedSections[section];
    });
  },
  
  setLoading: (loading: boolean) => {
    set((state) => {
      state.ui.loading = loading;
    });
  },
  
  setError: (error?: string) => {
    set((state) => {
      state.ui.error = error ? {
        message: error,
        timestamp: Date.now(),
      } : undefined;
    });
  },
  
  clearError: () => {
    set((state) => {
      state.ui.error = undefined;
    });
  },
  
  // Preferences actions
  updatePreferences: (preferences: Partial<UserPreferences>) => {
    set((state) => {
      Object.assign(state.ui.preferences, preferences);
    });
  },
});
```

## Atomic Selector Exports

### 1. Domain State Selectors

```typescript
// ✅ ATOMIC SELECTORS - Prevent unnecessary re-renders

// Core parameter selectors
export const useSearchQuery = () => useSearchStore(state => state.domain.query);
export const useSearchPage = () => useSearchStore(state => state.domain.page);
export const useSearchPageSize = () => useSearchStore(state => state.domain.pageSize);
export const useSemanticSearch = () => useSearchStore(state => state.domain.semantic);

// Field selection selectors
export const useSelectedFields = () => useSearchStore(state => state.domain.fields.selected);
export const useRawFieldsString = () => useSearchStore(state => state.domain.fields.raw);
export const useFieldAliases = () => useSearchStore(state => state.domain.fields.aliases);
export const useAvailableFields = () => useSearchStore(state => state.domain.fields.available);
export const useFieldCategories = () => useSearchStore(state => state.domain.fields.categories);

// Filter selectors
export const useTypeFilters = () => useSearchStore(state => state.domain.filters.type);
export const useExtensionFilters = () => useSearchStore(state => state.domain.filters.extension);
export const useSizeFilter = () => useSearchStore(state => state.domain.filters.size);
export const useDateFilter = () => useSearchStore(state => state.domain.filters.date);
export const useTextFilters = () => useSearchStore(state => state.domain.filters.text);
export const useAdvancedFilters = () => useSearchStore(state => state.domain.filters.advanced);

// Computed domain selectors
export const useHasActiveFilters = () => useSearchStore(state => {
  const { type, extension, size, date, text, advanced } = state.domain.filters;
  return (
    type.length > 0 ||
    extension.length > 0 ||
    size.range !== undefined ||
    date.range !== undefined ||
    Object.values(text).some(Boolean) ||
    advanced !== undefined
  );
});

export const useActiveFilterCount = () => useSearchStore(state => {
  const { type, extension, size, date, text, advanced } = state.domain.filters;
  let count = 0;
  if (type.length > 0) count++;
  if (extension.length > 0) count++;
  if (size.range) count++;
  if (date.range) count++;
  if (Object.values(text).some(Boolean)) count++;
  if (advanced) count++;
  return count;
});

export const useSearchSummary = () => useSearchStore(state => ({
  query: state.domain.query,
  hasQuery: state.domain.query.length > 0,
  hasFilters: state.actions.useHasActiveFilters(),
  fieldCount: state.domain.fields.selected.length,
  isEmpty: state.domain.query.length === 0 && !state.actions.useHasActiveFilters(),
}));
```

### 2. UI State Selectors

```typescript
// UI state atomic selectors
export const useFilterModalOpen = () => useSearchStore(state => state.ui.filterModalOpen);
export const useFilterModalDraft = () => useSearchStore(state => state.ui.filterModalDraft);
export const useExpandedSections = () => useSearchStore(state => state.ui.expandedSections);
export const useSearchLoading = () => useSearchStore(state => state.ui.loading);
export const useSearchError = () => useSearchStore(state => state.ui.error);
export const useSearchCount = () => useSearchStore(state => state.ui.searchCount);
export const useLastSearchTime = () => useSearchStore(state => state.ui.lastSearchTime);
export const useUserPreferences = () => useSearchStore(state => state.ui.preferences);

// UI computed selectors
export const useModalState = () => useSearchStore(state => ({
  isOpen: state.ui.filterModalOpen,
  isDirty: state.ui.filterModalDraft.isDirty,
  isValid: state.ui.filterModalDraft.isValid,
  hasErrors: Object.keys(state.ui.filterModalDraft.validationErrors).length > 0,
}));

export const useUIState = () => useSearchStore(state => ({
  loading: state.ui.loading,
  error: state.ui.error,
  hasError: state.ui.error !== undefined,
  searchCount: state.ui.searchCount,
}));
```

### 3. Action Selectors

```typescript
// Action selectors (grouped by domain)
export const useCoreActions = () => useSearchStore(state => ({
  setQuery: state.actions.setQuery,
  setPage: state.actions.setPage,
  setPageSize: state.actions.setPageSize,
  setSemantic: state.actions.setSemantic,
}));

export const useFieldActions = () => useSearchStore(state => ({
  setFields: state.actions.setFields,
  addField: state.actions.addField,
  removeField: state.actions.removeField,
  clearFields: state.actions.clearFields,
  resetFieldsToDefault: state.actions.resetFieldsToDefault,
}));

export const useFilterActions = () => useSearchStore(state => ({
  setTypeFilters: state.actions.setTypeFilters,
  setExtensionFilters: state.actions.setExtensionFilters,
  setSizeFilter: state.actions.setSizeFilter,
  setDateFilter: state.actions.setDateFilter,
  setTextFilters: state.actions.setTextFilters,
  setAdvancedFilters: state.actions.setAdvancedFilters,
  updateFilters: state.actions.updateFilters,
  clearFilters: state.actions.clearFilters,
}));

export const useUIActions = () => useSearchStore(state => ({
  openFilterModal: state.actions.openFilterModal,
  closeFilterModal: state.actions.closeFilterModal,
  updateFilterModalDraft: state.actions.updateFilterModalDraft,
  applyFilterModalDraft: state.actions.applyFilterModalDraft,
  discardFilterModalDraft: state.actions.discardFilterModalDraft,
  toggleSection: state.actions.toggleSection,
  setLoading: state.actions.setLoading,
  setError: state.actions.setError,
  clearError: state.actions.clearError,
}));

export const useSearchActions = () => useSearchStore(state => state.actions);
```

## Utility Functions

### 1. Parameter Transformation

```typescript
// Convert filters to API parameter format
export const transformFiltersToApiParams = (filters: FilterState) => ({
  // Comma-separated type filters
  type: filters.type.length > 0 ? filters.type.join(',') : undefined,
  
  // Comma-separated extension filters
  extension: filters.extension.length > 0 ? filters.extension.join(',') : undefined,
  
  // Grouped size filters
  size_range: filters.size.range ? formatSizeRange(filters.size.range) : undefined,
  size_unit: filters.size.range ? filters.size.unit : undefined,
  
  // Grouped date filters
  date_range: filters.date.range ? formatDateRange(filters.date.range) : undefined,
  date_field: filters.date.range ? filters.date.field : undefined,
  
  // Text filters (direct mapping)
  filename: filters.text.filename,
  path: filters.text.path,
  content: filters.text.content,
  
  // Advanced filters
  filters: filters.advanced?.encoded,
  filter_version: filters.advanced?.version,
});

// Format size range for API
const formatSizeRange = (range: { min?: number; max?: number }): string => {
  if (range.min !== undefined && range.max !== undefined) {
    return `${range.min}-${range.max}`;
  } else if (range.min !== undefined) {
    return `${range.min}-`;
  } else if (range.max !== undefined) {
    return `-${range.max}`;
  }
  return '';
};

// Format date range for API
const formatDateRange = (range: { start?: string; end?: string }): string => {
  if (range.start && range.end) {
    return `${range.start},${range.end}`;
  } else if (range.start) {
    return `${range.start},`;
  } else if (range.end) {
    return `,${range.end}`;
  }
  return '';
};

// Parse advanced filters
const parseAdvancedFilters = (encoded: string): Record<string, any> => {
  const filters: Record<string, any> = {};
  
  for (const filterGroup of encoded.split(';')) {
    if (!filterGroup.includes(':')) continue;
    
    const [key, values] = filterGroup.split(':', 2);
    const valueList = values.split(',').map(v => v.trim()).filter(Boolean);
    
    filters[key.trim()] = valueList;
  }
  
  return filters;
};
```

### 2. Form State Conversion

```typescript
// Convert filters to form state for modal
const convertFiltersToFormState = (filters: FilterState): FilterModalFormState => ({
  selectedTypes: [...filters.type],
  selectedExtensions: [...filters.extension],
  sizeMin: filters.size.range?.min,
  sizeMax: filters.size.range?.max,
  sizeUnit: filters.size.unit,
  dateStart: filters.date.range?.start,
  dateEnd: filters.date.range?.end,
  dateField: filters.date.field,
  filename: filters.text.filename,
  path: filters.text.path,
  content: filters.text.content,
  isDirty: false,
  isValid: true,
  validationErrors: {},
});

// Convert form state back to filters
const convertFormStateToFilters = (formState: FilterModalFormState): FilterState => ({
  type: formState.selectedTypes,
  extension: formState.selectedExtensions,
  size: {
    range: (formState.sizeMin !== undefined || formState.sizeMax !== undefined) ? {
      min: formState.sizeMin,
      max: formState.sizeMax,
    } : undefined,
    unit: formState.sizeUnit,
  },
  date: {
    range: (formState.dateStart || formState.dateEnd) ? {
      start: formState.dateStart,
      end: formState.dateEnd,
    } : undefined,
    field: formState.dateField,
  },
  text: {
    filename: formState.filename,
    path: formState.path,
    content: formState.content,
  },
});

// Create empty filter draft
const createEmptyFilterDraft = (): FilterModalFormState => ({
  selectedTypes: [],
  selectedExtensions: [],
  sizeUnit: 'B',
  dateField: 'ingested',
  isDirty: false,
  isValid: true,
  validationErrors: {},
});

// Validate filter draft
const validateFilterDraft = (draft: FilterModalFormState): boolean => {
  const errors: Record<string, string> = {};
  
  // Validate size range
  if (draft.sizeMin !== undefined && draft.sizeMax !== undefined) {
    if (draft.sizeMin > draft.sizeMax) {
      errors.sizeRange = 'Minimum size cannot be greater than maximum size';
    }
  }
  
  // Validate date range
  if (draft.dateStart && draft.dateEnd) {
    if (new Date(draft.dateStart) > new Date(draft.dateEnd)) {
      errors.dateRange = 'Start date cannot be after end date';
    }
  }
  
  draft.validationErrors = errors;
  return Object.keys(errors).length === 0;
};
```

## Performance Optimizations

### 1. Subscription Management

```typescript
// Subscribe to specific state changes for performance monitoring
export const useSearchPerformanceMonitoring = () => {
  useEffect(() => {
    const unsubscribe = useSearchStore.subscribe(
      (state) => state.domain.query,
      (query, prevQuery) => {
        if (query !== prevQuery && query.length > 0) {
          // Track search performance
          performance.mark('search-start');
        }
      }
    );
    
    return unsubscribe;
  }, []);
};

// Subscribe to filter changes for analytics
export const useFilterAnalytics = () => {
  useEffect(() => {
    const unsubscribe = useSearchStore.subscribe(
      (state) =>