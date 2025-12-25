// Dashboard feature public exports

export * from "./types";
export {
  useDashboardStore,
  useAvailableWidgets,
  useDashboardActions,
  useExpandedWidget,
  useWidgetSelectorOpen,
  WIDGET_DEFINITIONS,
  DEFAULT_LAYOUT,
} from "./store/dashboardStore";
export * from "./components";
export { useDashboardLayout } from "./hooks/useDashboardLayout";
export {
  useWidgetData,
  useFavoritesWidgetData,
  useCollectionsWidgetData,
  useRecentAssetsWidgetData,
} from "./hooks/useWidgetData";
