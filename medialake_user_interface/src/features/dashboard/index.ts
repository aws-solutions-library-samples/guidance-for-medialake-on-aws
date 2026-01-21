// Dashboard feature public exports

export * from "./types";
export {
  useDashboardStore,
  useAvailableWidgets,
  useDashboardActions,
  useExpandedWidget,
  useWidgetSelectorOpen,
  useDashboardSyncState,
  WIDGET_DEFINITIONS,
  DEFAULT_LAYOUT,
  convertApiLayoutToFrontend,
  convertFrontendLayoutToApi,
} from "./store/dashboardStore";
export * from "./components";
export { useDashboardLayout } from "./hooks/useDashboardLayout";
export { useDashboardSync } from "./hooks/useDashboardSync";
export {
  useWidgetData,
  useFavoritesWidgetData,
  useCollectionsWidgetData,
  useRecentAssetsWidgetData,
} from "./hooks/useWidgetData";
