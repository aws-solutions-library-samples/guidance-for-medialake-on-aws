// Dashboard feature type definitions

// Collection view types for the collections widget
export type CollectionViewType =
  | "all"
  | "public"
  | "private"
  | "my-collections"
  | "shared-with-me"
  | "my-shared";

// Sorting configuration types
export type SortBy = "name" | "createdAt" | "updatedAt";
export type SortOrder = "asc" | "desc";

export interface SortConfig {
  sortBy: SortBy;
  sortOrder: SortOrder;
}

// Collections widget configuration
export interface CollectionsWidgetConfig {
  viewType: CollectionViewType;
  sorting: SortConfig;
}

export type WidgetType = "favorites" | "collections" | "recent-assets";

export interface WidgetDefinition {
  type: WidgetType;
  title: string;
  description: string;
  icon: string;
  defaultSize: { w: number; h: number };
  minSize: { w: number; h: number };
  maxSize: { w: number; h: number };
  defaultConfig?: CollectionsWidgetConfig;
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
  static?: boolean;
}

export interface DashboardLayout {
  version: number;
  layoutVersion?: number; // API uses layoutVersion, frontend uses version
  widgets: WidgetInstance[];
  layouts: {
    lg: LayoutItem[];
    md: LayoutItem[];
    sm: LayoutItem[];
  };
  updatedAt?: string;
}

export interface WidgetInstance {
  id: string;
  type: WidgetType;
  config?: CollectionsWidgetConfig;
}

export interface DashboardState {
  layout: DashboardLayout;
  isEditMode: boolean;
  expandedWidgetId: string | null;
  isWidgetSelectorOpen: boolean;
}

export interface DashboardActions {
  setLayout: (layout: DashboardLayout) => void;
  updateLayoutItem: (itemId: string, updates: Partial<LayoutItem>) => void;
  addWidget: (type: WidgetType) => void;
  removeWidget: (widgetId: string) => void;
  updateWidgetConfig: (widgetId: string, config: CollectionsWidgetConfig) => void;
  resetToDefault: () => void;
  setExpandedWidget: (widgetId: string | null) => void;
  toggleWidgetSelector: () => void;
  setWidgetSelectorOpen: (isOpen: boolean) => void;
  saveLayout: () => void;
  loadLayout: () => void;
}

export interface BaseWidgetProps {
  widgetId: string;
  isExpanded?: boolean;
  onDataLoad?: () => void;
  onError?: (error: Error) => void;
}

export interface WidgetContainerProps {
  widgetId: string;
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  onExpand?: () => void;
  onRefresh?: () => void;
  onRemove?: () => void;
  isLoading?: boolean;
  isExpanded?: boolean;
}

export interface WidgetHeaderProps {
  title: string;
  icon: React.ReactNode;
  onExpand?: () => void;
  onRefresh?: () => void;
  onRemove?: () => void;
  isLoading?: boolean;
  isDraggable?: boolean;
}

export interface WidgetSelectorProps {
  isOpen: boolean;
  onClose: () => void;
  availableWidgets: WidgetDefinition[];
  onAddWidget: (widgetType: WidgetType) => void;
}

export interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
}
