import React, { useEffect, useState } from "react";
import { useLocation } from "react-router";
import { useTranslation } from "react-i18next";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Grid,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Paper,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  Bookmark as SavedIcon,
  Check as ConfirmIcon,
  Close as CancelIcon,
  DeleteOutline as DeleteIcon,
  Edit as RenameIcon,
  History as HistoryIcon,
} from "@mui/icons-material";
import { ConfirmationModal } from "@/components/common/ConfirmationModal";
import { formatLocalDateTime, formatRelativeTime } from "@/shared/utils/dateUtils";
import {
  useClearSearchHistory,
  useDeleteSavedSearch,
  useRemoveHistoryEntry,
  useRenameSavedSearch,
  useSavedSearches,
  useSearchHistory,
  type SavedSearch,
} from "../api";
import { useRunSearch } from "../hooks";
import { describeDefinition, type SearchDefinition } from "../searchDefinition";

const MAX_NAME_LENGTH = 100;

/**
 * Profile page panels for the user's saved searches and recent searches.
 * Every row runs its search when clicked.
 */
export const SearchHistoryProfileSection: React.FC = () => {
  const { t } = useTranslation();
  const saved = useSavedSearches();
  const history = useSearchHistory();
  const runSearch = useRunSearch();
  const rename = useRenameSavedSearch();
  const remove = useDeleteSavedSearch();
  const removeEntry = useRemoveHistoryEntry();
  const clearHistory = useClearSearchHistory();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftName, setDraftName] = useState("");
  const [pendingDelete, setPendingDelete] = useState<SavedSearch | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);

  // "Manage saved searches" links here with #saved-searches; scroll to it once
  // the lists have loaded (a client-side route change doesn't do this itself).
  const { hash } = useLocation();
  const listsReady = !saved.isLoading && !history.isLoading;
  useEffect(() => {
    if (!listsReady || (hash !== "#saved-searches" && hash !== "#recent-searches")) return;
    document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [hash, listsReady]);

  const details = (definition: SearchDefinition, includeQuery: boolean) =>
    [includeQuery ? definition.q : "", ...describeDefinition(definition, t)]
      .filter(Boolean)
      .join(" · ");

  const startRename = (item: SavedSearch) => {
    setEditingId(item.id);
    setDraftName(item.name);
  };

  const commitRename = () => {
    const name = draftName.trim();
    if (!editingId || !name || name.length > MAX_NAME_LENGTH) return;
    rename.mutate({ id: editingId, name });
    setEditingId(null);
  };

  const timestamp = (iso: string) => (
    <Tooltip title={formatLocalDateTime(iso)}>
      <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: "nowrap" }}>
        {formatRelativeTime(iso)}
      </Typography>
    </Tooltip>
  );

  const loadingOrError = (query: { isLoading: boolean; error: Error | null }) => {
    if (query.isLoading) return <CircularProgress size={24} sx={{ m: 2 }} />;
    if (query.error)
      return (
        <Alert severity="warning" sx={{ mt: 1 }}>
          {t("search.history.loadFailed", "Couldn't load this list. Try again later.")}
        </Alert>
      );
    return null;
  };

  return (
    <Grid container spacing={3} sx={{ mt: 3 }}>
      <Grid size={{ xs: 12, md: 6 }}>
        <Paper sx={{ p: 3, height: "100%" }} id="saved-searches">
          <Typography variant="h6" component="h2" gutterBottom>
            {t("search.saved.title", "Saved searches")}
          </Typography>
          {loadingOrError(saved) ??
            (saved.data?.length ? (
              <List dense aria-label={t("search.saved.title", "Saved searches")}>
                {saved.data.map((item) =>
                  editingId === item.id ? (
                    <ListItem key={item.id} disableGutters>
                      <Box
                        component="form"
                        onSubmit={(e: React.FormEvent) => {
                          e.preventDefault();
                          commitRename();
                        }}
                        sx={{ display: "flex", alignItems: "center", gap: 1, width: "100%" }}
                      >
                        <TextField
                          autoFocus
                          size="small"
                          fullWidth
                          value={draftName}
                          onChange={(e) => setDraftName(e.target.value)}
                          onKeyDown={(e) => e.key === "Escape" && setEditingId(null)}
                          error={draftName.trim().length > MAX_NAME_LENGTH || !draftName.trim()}
                          inputProps={{
                            "aria-label": t("search.saved.nameLabel", "Name"),
                          }}
                        />
                        <IconButton
                          type="submit"
                          size="small"
                          aria-label={t("common.save", "Save")}
                          disabled={!draftName.trim() || draftName.trim().length > MAX_NAME_LENGTH}
                        >
                          <ConfirmIcon fontSize="small" />
                        </IconButton>
                        <IconButton
                          size="small"
                          aria-label={t("common.cancel", "Cancel")}
                          onClick={() => setEditingId(null)}
                        >
                          <CancelIcon fontSize="small" />
                        </IconButton>
                      </Box>
                    </ListItem>
                  ) : (
                    <ListItem
                      key={item.id}
                      disablePadding
                      secondaryAction={
                        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                          {timestamp(item.updatedAt)}
                          <Tooltip title={t("search.saved.rename", "Rename")}>
                            <IconButton
                              size="small"
                              aria-label={t("search.saved.renameNamed", "Rename {{name}}", {
                                name: item.name,
                              })}
                              onClick={() => startRename(item)}
                            >
                              <RenameIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                          <Tooltip title={t("common.delete", "Delete")}>
                            <IconButton
                              size="small"
                              aria-label={t("search.saved.deleteNamed", "Delete {{name}}", {
                                name: item.name,
                              })}
                              onClick={() => setPendingDelete(item)}
                            >
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      }
                    >
                      <ListItemButton onClick={() => runSearch(item.definition)} sx={{ pr: 20 }}>
                        <ListItemIcon sx={{ minWidth: 36 }}>
                          <SavedIcon fontSize="small" color="primary" />
                        </ListItemIcon>
                        <ListItemText
                          primary={item.name}
                          secondary={details(item.definition, true) || undefined}
                          primaryTypographyProps={{ noWrap: true }}
                          secondaryTypographyProps={{ noWrap: true }}
                        />
                      </ListItemButton>
                    </ListItem>
                  )
                )}
              </List>
            ) : (
              <Typography variant="body2" color="text.secondary">
                {t(
                  "search.saved.empty",
                  "You haven't saved any searches yet. Run a search and choose “Save search” to keep it here."
                )}
              </Typography>
            ))}
        </Paper>
      </Grid>

      <Grid size={{ xs: 12, md: 6 }}>
        <Paper sx={{ p: 3, height: "100%" }} id="recent-searches">
          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <Typography variant="h6" component="h2" gutterBottom>
              {t("search.history.title", "Recent searches")}
            </Typography>
            {!!history.data?.length && (
              <Button size="small" onClick={() => setConfirmClear(true)}>
                {t("search.history.clear", "Clear history")}
              </Button>
            )}
          </Box>
          {loadingOrError(history) ??
            (history.data?.length ? (
              <List dense aria-label={t("search.history.title", "Recent searches")}>
                {history.data.map((entry) => {
                  const label = entry.definition.q || t("search.history.allAssets", "All assets");
                  return (
                    <ListItem
                      key={entry.fingerprint}
                      disablePadding
                      secondaryAction={
                        <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                          {timestamp(entry.searchedAt)}
                          <Tooltip title={t("search.history.remove", "Remove from history")}>
                            <IconButton
                              size="small"
                              aria-label={t(
                                "search.history.removeNamed",
                                "Remove {{query}} from history",
                                { query: label }
                              )}
                              onClick={() => removeEntry.mutate(entry.fingerprint)}
                            >
                              <CancelIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </Box>
                      }
                    >
                      <ListItemButton onClick={() => runSearch(entry.definition)} sx={{ pr: 14 }}>
                        <ListItemIcon sx={{ minWidth: 36 }}>
                          <HistoryIcon fontSize="small" />
                        </ListItemIcon>
                        <ListItemText
                          primary={label}
                          secondary={details(entry.definition, false) || undefined}
                          primaryTypographyProps={{ noWrap: true }}
                          secondaryTypographyProps={{ noWrap: true }}
                        />
                      </ListItemButton>
                    </ListItem>
                  );
                })}
              </List>
            ) : (
              <Typography variant="body2" color="text.secondary">
                {t("search.history.empty", "Your last five searches will appear here.")}
              </Typography>
            ))}
        </Paper>
      </Grid>

      <ConfirmationModal
        open={!!pendingDelete}
        title={t("search.saved.deleteTitle", "Delete saved search")}
        message={t("search.saved.deleteConfirm", "Delete “{{name}}”? This can't be undone.", {
          name: pendingDelete?.name ?? "",
        })}
        confirmText={t("common.delete", "Delete")}
        cancelText={t("common.cancel", "Cancel")}
        onCancel={() => setPendingDelete(null)}
        onConfirm={() => {
          if (pendingDelete) remove.mutate(pendingDelete.id);
          setPendingDelete(null);
        }}
      />
      <ConfirmationModal
        open={confirmClear}
        title={t("search.history.clearTitle", "Clear search history")}
        message={t(
          "search.history.clearConfirm",
          "Remove all of your recent searches? Saved searches are not affected."
        )}
        confirmText={t("search.history.clear", "Clear history")}
        cancelText={t("common.cancel", "Cancel")}
        onCancel={() => setConfirmClear(false)}
        onConfirm={() => {
          clearHistory.mutate();
          setConfirmClear(false);
        }}
      />
    </Grid>
  );
};

export default SearchHistoryProfileSection;
