import React, { useCallback } from "react";
import { useTranslation } from "react-i18next";
import {
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Tooltip,
  Typography,
} from "@mui/material";
import { Bookmark as SavedSearchIcon } from "@mui/icons-material";
import { formatLocalDateTime, formatRelativeTime } from "@/shared/utils/dateUtils";
import { useSavedSearches } from "@/features/search-history/api";
import { useRunSearch } from "@/features/search-history/hooks";
import { describeDefinition } from "@/features/search-history/searchDefinition";
import { WidgetContainer } from "../WidgetContainer";
import { EmptyState } from "../EmptyState";
import { useDashboardActions, useDashboardStore } from "../../store/dashboardStore";
import type { BaseWidgetProps } from "../../types";

/**
 * Dashboard widget listing the user's saved searches. Clicking one runs it,
 * taking the user straight to its results.
 */
export const SavedSearchesWidget: React.FC<BaseWidgetProps> = ({
  widgetId,
  isExpanded = false,
}) => {
  const { t } = useTranslation();
  const { removeWidget, setExpandedWidget } = useDashboardActions();
  const customName = useDashboardStore(
    (state) => state.layout.widgets.find((w) => w.id === widgetId)?.customName
  );
  const { data: savedSearches = [], isLoading, error, refetch } = useSavedSearches();
  const runSearch = useRunSearch();

  const handleRefresh = useCallback(() => {
    refetch();
  }, [refetch]);
  const handleExpand = useCallback(
    () => setExpandedWidget(widgetId),
    [setExpandedWidget, widgetId]
  );
  const handleRemove = useCallback(() => removeWidget(widgetId), [removeWidget, widgetId]);

  const renderContent = () => {
    if (isLoading) return null;
    if (savedSearches.length === 0) {
      return (
        <EmptyState
          icon={<SavedSearchIcon sx={{ fontSize: 48 }} />}
          title={t("dashboard.widgets.savedSearches.emptyTitle", "No saved searches")}
          description={t(
            "dashboard.widgets.savedSearches.emptyDescription",
            "Run a search and choose “Save search” to keep it here."
          )}
        />
      );
    }
    return (
      <List dense disablePadding aria-label={t("search.saved.title", "Saved searches")}>
        {savedSearches.map((saved) => {
          const details = [saved.definition.q, ...describeDefinition(saved.definition, t)]
            .filter(Boolean)
            .join(" · ");
          return (
            <ListItemButton
              key={saved.id}
              onClick={() => runSearch(saved.definition)}
              sx={{ borderRadius: 1 }}
            >
              <ListItemIcon sx={{ minWidth: 36 }}>
                <SavedSearchIcon fontSize="small" color="primary" />
              </ListItemIcon>
              <ListItemText
                primary={saved.name}
                secondary={details || undefined}
                primaryTypographyProps={{ noWrap: true }}
                secondaryTypographyProps={{ noWrap: true }}
              />
              <Tooltip title={formatLocalDateTime(saved.updatedAt)}>
                <Typography variant="caption" color="text.secondary" sx={{ ml: 1, flexShrink: 0 }}>
                  {formatRelativeTime(saved.updatedAt)}
                </Typography>
              </Tooltip>
            </ListItemButton>
          );
        })}
      </List>
    );
  };

  return (
    <WidgetContainer
      widgetId={widgetId}
      title={customName || t("dashboard.widgets.savedSearches.title", "Saved Searches")}
      icon={<SavedSearchIcon />}
      onExpand={handleExpand}
      onRefresh={handleRefresh}
      onRemove={handleRemove}
      isLoading={isLoading}
      isExpanded={isExpanded}
      error={error}
      onRetry={handleRefresh}
    >
      {renderContent()}
    </WidgetContainer>
  );
};

export default SavedSearchesWidget;
