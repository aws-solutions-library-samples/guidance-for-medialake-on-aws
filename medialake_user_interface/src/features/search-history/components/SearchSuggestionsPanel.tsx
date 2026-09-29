import React from "react";
import { useTranslation } from "react-i18next";
import { Box, ClickAwayListener, IconButton, Link, Paper, Popper, Tooltip } from "@mui/material";
import { alpha, useTheme } from "@mui/material/styles";
import {
  Bookmark as SavedIcon,
  Close as RemoveIcon,
  History as HistoryIcon,
} from "@mui/icons-material";
import { formatRelativeTime } from "@/shared/utils/dateUtils";
import { describeDefinition } from "../searchDefinition";
import type { SuggestionItem } from "../hooks";

export const SUGGESTIONS_LISTBOX_ID = "search-suggestions-listbox";
export const suggestionOptionId = (item: SuggestionItem) => `search-suggestion-${item.id}`;

interface SearchSuggestionsPanelProps {
  open: boolean;
  anchorEl: HTMLElement | null;
  savedItems: SuggestionItem[];
  historyItems: SuggestionItem[];
  totalSaved: number;
  activeId: string | null;
  onSelect: (item: SuggestionItem) => void;
  onRemoveHistory: (fingerprint: string) => void;
  onClearHistory: () => void;
  onManage: () => void;
  onClose: () => void;
  /** Hover moves the keyboard highlight, like a native listbox. */
  onHover: (id: string) => void;
}

/**
 * Dropdown under the search box listing the user's saved searches and recent
 * searches. It renders nothing when both lists are empty.
 *
 * The search input owns focus and keyboard handling (combobox pattern); this
 * panel is the listbox it controls, so options are never focused directly.
 */
export const SearchSuggestionsPanel: React.FC<SearchSuggestionsPanelProps> = ({
  open,
  anchorEl,
  savedItems,
  historyItems,
  totalSaved,
  activeId,
  onSelect,
  onRemoveHistory,
  onClearHistory,
  onManage,
  onClose,
  onHover,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";

  if (!open || !anchorEl || savedItems.length + historyItems.length === 0) return null;

  const sectionLabel = (text: string, id: string) => (
    <Box
      id={id}
      role="presentation"
      sx={{
        px: 2,
        pt: 1.25,
        pb: 0.5,
        fontSize: "11px",
        fontWeight: 600,
        textTransform: "uppercase",
        letterSpacing: "0.05em",
        color: alpha(theme.palette.text.secondary, 0.7),
      }}
    >
      {text}
    </Box>
  );

  const renderOption = (item: SuggestionItem) => {
    const isActive = item.id === activeId;
    const chips = describeDefinition(item.definition, t);
    const isSaved = item.kind === "saved";
    const primary = isSaved
      ? item.saved.name
      : item.definition.q || t("search.history.allAssets", "All assets");
    const secondary = isSaved
      ? [item.definition.q, ...chips].filter(Boolean).join(" · ")
      : chips.join(" · ");

    return (
      <Box
        key={item.id}
        id={suggestionOptionId(item)}
        role="option"
        aria-selected={isActive}
        // Saved rows are one line and cut the details off; show them in full
        // on hover. (Screen readers get the whole text regardless.)
        title={isSaved && secondary ? `${primary} — ${secondary}` : undefined}
        // Keep focus in the input; selection happens on click.
        onMouseDown={(e) => e.preventDefault()}
        onClick={() => onSelect(item)}
        onMouseEnter={() => onHover(item.id)}
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1.5,
          px: 2,
          py: 0.75,
          cursor: "pointer",
          backgroundColor: isActive
            ? alpha(theme.palette.primary.main, isDark ? 0.16 : 0.08)
            : "transparent",
        }}
      >
        {isSaved ? (
          <SavedIcon fontSize="small" sx={{ color: theme.palette.primary.main }} />
        ) : (
          <HistoryIcon fontSize="small" sx={{ color: theme.palette.text.secondary }} />
        )}
        <Box
          data-testid="suggestion-text"
          sx={
            isSaved
              ? {
                  // One line: name, then the query/filters in muted text. The
                  // name keeps up to 60% of the row; the details take the rest
                  // and are cut off with an ellipsis.
                  minWidth: 0,
                  flex: 1,
                  display: "flex",
                  alignItems: "baseline",
                  gap: 1,
                  overflow: "hidden",
                }
              : { minWidth: 0, flex: 1 }
          }
        >
          <Box
            sx={{
              fontSize: "14px",
              color: theme.palette.text.primary,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              ...(isSaved && { flexShrink: 0, maxWidth: "60%" }),
            }}
          >
            {primary}
          </Box>
          {secondary && (
            <Box
              sx={{
                fontSize: "12px",
                color: theme.palette.text.secondary,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                ...(isSaved && { minWidth: 0, flex: 1 }),
              }}
            >
              {secondary}
            </Box>
          )}
        </Box>
        {item.kind === "history" && (
          <>
            <Box
              component="span"
              sx={{ fontSize: "12px", color: theme.palette.text.disabled, whiteSpace: "nowrap" }}
            >
              {formatRelativeTime(item.entry.searchedAt)}
            </Box>
            <Tooltip title={t("search.history.remove", "Remove from history")}>
              <IconButton
                size="small"
                aria-label={t("search.history.removeNamed", "Remove {{query}} from history", {
                  query: primary,
                })}
                // Not reachable by Tab: the input keeps focus (combobox pattern);
                // keyboard users remove entries with Delete on the highlighted row.
                tabIndex={-1}
                onMouseDown={(e) => e.preventDefault()}
                onClick={(e) => {
                  e.stopPropagation();
                  onRemoveHistory(item.entry.fingerprint);
                }}
                sx={{ p: 0.5 }}
              >
                <RemoveIcon sx={{ fontSize: 16 }} />
              </IconButton>
            </Tooltip>
          </>
        )}
      </Box>
    );
  };

  return (
    <Popper
      open
      anchorEl={anchorEl}
      placement="bottom-start"
      sx={{ zIndex: theme.zIndex.modal + 1, width: anchorEl.clientWidth }}
    >
      <ClickAwayListener
        onClickAway={(event) => {
          // Clicking back into the search box keeps the list open.
          if (anchorEl.contains(event.target as Node)) return;
          onClose();
        }}
      >
        <Paper
          elevation={0}
          onMouseDown={(e) => e.preventDefault()}
          sx={{
            mt: 1,
            borderRadius: "12px",
            overflow: "hidden",
            border: `1px solid ${alpha(theme.palette.divider, isDark ? 0.12 : 0.1)}`,
            boxShadow: `0 8px 24px ${alpha(theme.palette.common.black, isDark ? 0.5 : 0.12)}`,
            pb: 0.5,
          }}
        >
          <Box
            id={SUGGESTIONS_LISTBOX_ID}
            role="listbox"
            aria-label={t("search.history.suggestionsLabel", "Saved and recent searches")}
          >
            {savedItems.length > 0 && (
              <Box role="group" aria-labelledby="search-suggestions-saved">
                {sectionLabel(
                  t("search.saved.title", "Saved searches"),
                  "search-suggestions-saved"
                )}
                {savedItems.map(renderOption)}
              </Box>
            )}
            {historyItems.length > 0 && (
              <Box role="group" aria-labelledby="search-suggestions-recent">
                {sectionLabel(
                  t("search.history.title", "Recent searches"),
                  "search-suggestions-recent"
                )}
                {historyItems.map(renderOption)}
              </Box>
            )}
          </Box>
          <Box
            sx={{
              display: "flex",
              justifyContent: "space-between",
              gap: 2,
              px: 2,
              pt: 0.75,
              mt: 0.5,
              borderTop: `1px solid ${alpha(theme.palette.divider, 0.08)}`,
              fontSize: "12px",
            }}
          >
            <Link component="button" type="button" underline="hover" onClick={onManage}>
              {totalSaved > savedItems.length
                ? t("search.saved.seeAll", "See all {{count}} saved searches", {
                    count: totalSaved,
                  })
                : t("search.saved.manage", "Manage saved searches")}
            </Link>
            {historyItems.length > 0 && (
              <Link
                component="button"
                type="button"
                underline="hover"
                color="text.secondary"
                onClick={onClearHistory}
              >
                {t("search.history.clear", "Clear history")}
              </Link>
            )}
          </Box>
        </Paper>
      </ClickAwayListener>
    </Popper>
  );
};

export default SearchSuggestionsPanel;
