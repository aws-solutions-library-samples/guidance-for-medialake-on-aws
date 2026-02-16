import React, { useState, useMemo, useEffect } from "react";
import {
  Box,
  Button,
  Typography,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  CircularProgress,
  Alert,
  InputAdornment,
  Snackbar,
  alpha,
  Chip,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Tooltip,
  TableSortLabel,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import SearchIcon from "@mui/icons-material/Search";
import FilterListIcon from "@mui/icons-material/FilterList";
import VpnKeyIcon from "@mui/icons-material/VpnKey";
import VisibilityIcon from "@mui/icons-material/Visibility";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import { useTranslation } from "react-i18next";
import { Can } from "@/permissions/components/Can";
import { useGetApiKeys } from "@/api/hooks/useApiKeys";
import { useErrorModal } from "@/hooks/useErrorModal";
import { ApiKey } from "@/api/types/apiKey.types";
import { formatRelativeTime, formatLocalDateTime } from "@/shared/utils/dateUtils";
import ApiKeyFormDialog from "./ApiKeyFormDialog";
import DeleteApiKeyDialog from "./DeleteApiKeyDialog";
import ApiKeyDetailsDialog from "./ApiKeyDetailsDialog";
import { EmptyTableState } from "@/components/common/table";

type SortField = "name" | "status" | "scope" | "createdAt" | "lastUsed";
type SortDirection = "asc" | "desc";

const ApiKeyManagement: React.FC = () => {
  const { t } = useTranslation();
  const [searchTerm, setSearchTerm] = useState("");
  const [filterCategory, setFilterCategory] = useState("all");
  const [selectedApiKey, setSelectedApiKey] = useState<ApiKey | null>(null);
  const [isFormDialogOpen, setIsFormDialogOpen] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isDetailsDialogOpen, setIsDetailsDialogOpen] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [snackbarOpen, setSnackbarOpen] = useState(false);
  const [snackbarMessage, setSnackbarMessage] = useState("");
  const [snackbarSeverity, setSnackbarSeverity] = useState<"success" | "error">("success");
  const [sortField, setSortField] = useState<SortField>("createdAt");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  const { showError } = useErrorModal();
  const { data: apiKeys = [], isLoading, error } = useGetApiKeys(true);

  // Filter and sort
  const filteredApiKeys = useMemo(() => {
    let filtered = apiKeys;

    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      filtered = filtered.filter(
        (k) => k.name.toLowerCase().includes(term) || k.description.toLowerCase().includes(term)
      );
    }

    if (filterCategory !== "all") {
      filtered = filtered.filter((k) => {
        if (filterCategory === "enabled") return k.isEnabled;
        if (filterCategory === "disabled") return !k.isEnabled;
        return true;
      });
    }

    // Sort
    const sorted = [...filtered].sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case "name":
          cmp = a.name.localeCompare(b.name);
          break;
        case "status":
          cmp = Number(b.isEnabled) - Number(a.isEnabled);
          break;
        case "scope":
          cmp = (a.scope || "").localeCompare(b.scope || "");
          break;
        case "createdAt":
          cmp = new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime();
          break;
        case "lastUsed":
          cmp = new Date(a.lastUsed || 0).getTime() - new Date(b.lastUsed || 0).getTime();
          break;
      }
      return sortDirection === "asc" ? cmp : -cmp;
    });

    return sorted;
  }, [apiKeys, searchTerm, filterCategory, sortField, sortDirection]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDirection("asc");
    }
  };

  // Event handlers
  const handleAddApiKey = () => {
    setSelectedApiKey(null);
    setIsEditMode(false);
    setIsFormDialogOpen(true);
  };

  const handleEditApiKey = (apiKey: ApiKey) => {
    setSelectedApiKey(apiKey);
    setIsEditMode(true);
    setIsFormDialogOpen(true);
  };

  const handleViewApiKey = (apiKey: ApiKey) => {
    setSelectedApiKey(apiKey);
    setIsDetailsDialogOpen(true);
  };

  const handleDeleteApiKey = (apiKey: ApiKey) => {
    setSelectedApiKey(apiKey);
    setIsDeleteDialogOpen(true);
  };

  const handleFormDialogClose = () => {
    setIsFormDialogOpen(false);
    setSelectedApiKey(null);
    setIsEditMode(false);
  };

  const handleFormDialogSuccess = (message: string) => {
    setSnackbarMessage(message);
    setSnackbarSeverity("success");
    setSnackbarOpen(true);
    handleFormDialogClose();
  };

  const handleDeleteDialogClose = () => {
    setIsDeleteDialogOpen(false);
    setSelectedApiKey(null);
  };

  const handleDeleteDialogSuccess = () => {
    setSnackbarMessage("API key deleted successfully");
    setSnackbarSeverity("success");
    setSnackbarOpen(true);
    handleDeleteDialogClose();
  };

  const handleDetailsDialogClose = () => {
    setIsDetailsDialogOpen(false);
    setSelectedApiKey(null);
  };

  const handleDetailsDialogEdit = (apiKey: ApiKey) => {
    setSelectedApiKey(apiKey);
    setIsEditMode(true);
    setIsDetailsDialogOpen(false);
    setIsFormDialogOpen(true);
  };

  const handleSnackbarClose = () => {
    setSnackbarOpen(false);
  };

  useEffect(() => {
    if (error) {
      showError(`Failed to fetch API keys: ${error.message}`);
    }
  }, [error, showError]);

  return (
    <Box>
      {/* Header */}
      <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={3}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 0.5 }}>
            {t("apiKeys.title")}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {t("apiKeys.description")}
          </Typography>
        </Box>
        <Can I="create" a="api-key">
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleAddApiKey}
            sx={{ flexShrink: 0 }}
          >
            {t("apiKeys.addApiKey")}
          </Button>
        </Can>
      </Box>

      {/* Search and Filter Bar */}
      <Box
        sx={{
          display: "flex",
          gap: 2,
          mb: 2,
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        <TextField
          size="small"
          placeholder={t("apiKeys.searchPlaceholder")}
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon sx={{ fontSize: 20, color: "text.disabled" }} />
              </InputAdornment>
            ),
          }}
          sx={{ minWidth: 260, flex: 1, maxWidth: 400 }}
        />
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <InputLabel shrink sx={{ backgroundColor: "background.paper", px: 0.5 }}>
            {t("common.labels.status")}
          </InputLabel>
          <Select
            value={filterCategory}
            label={t("common.labels.status")}
            onChange={(e) => setFilterCategory(e.target.value)}
            startAdornment={
              <InputAdornment position="start">
                <FilterListIcon sx={{ fontSize: 18, color: "text.disabled" }} />
              </InputAdornment>
            }
            notched
          >
            <MenuItem value="all">{t("apiKeys.categoryAll")}</MenuItem>
            <MenuItem value="enabled">{t("common.enabled")}</MenuItem>
            <MenuItem value="disabled">{t("common.disabled")}</MenuItem>
          </Select>
        </FormControl>

        {!isLoading && !error && apiKeys.length > 0 && (
          <Chip
            label={`${filteredApiKeys.length} of ${apiKeys.length}`}
            size="small"
            variant="outlined"
            sx={{ ml: "auto" }}
          />
        )}
      </Box>

      {/* Loading */}
      {isLoading && (
        <Box display="flex" justifyContent="center" py={6}>
          <CircularProgress />
        </Box>
      )}

      {/* Error */}
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Failed to load API keys. Please try again.
        </Alert>
      )}

      {/* Table */}
      {!isLoading && !error && (
        <TableContainer
          component={Paper}
          elevation={1}
          sx={{ borderRadius: 2, overflow: "hidden" }}
        >
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600 }}>
                  <TableSortLabel
                    active={sortField === "name"}
                    direction={sortField === "name" ? sortDirection : "asc"}
                    onClick={() => handleSort("name")}
                  >
                    {t("common.name")}
                  </TableSortLabel>
                </TableCell>
                <TableCell sx={{ fontWeight: 600 }}>
                  <TableSortLabel
                    active={sortField === "status"}
                    direction={sortField === "status" ? sortDirection : "asc"}
                    onClick={() => handleSort("status")}
                  >
                    {t("common.labels.status")}
                  </TableSortLabel>
                </TableCell>
                <TableCell sx={{ fontWeight: 600 }}>
                  <TableSortLabel
                    active={sortField === "scope"}
                    direction={sortField === "scope" ? sortDirection : "asc"}
                    onClick={() => handleSort("scope")}
                  >
                    {t("apiKeys.details.scope", "Scope")}
                  </TableSortLabel>
                </TableCell>
                <TableCell sx={{ fontWeight: 600 }}>
                  <TableSortLabel
                    active={sortField === "createdAt"}
                    direction={sortField === "createdAt" ? sortDirection : "asc"}
                    onClick={() => handleSort("createdAt")}
                  >
                    {t("apiKeys.details.created", "Created")}
                  </TableSortLabel>
                </TableCell>
                <TableCell sx={{ fontWeight: 600 }}>
                  <TableSortLabel
                    active={sortField === "lastUsed"}
                    direction={sortField === "lastUsed" ? sortDirection : "asc"}
                    onClick={() => handleSort("lastUsed")}
                  >
                    {t("apiKeys.details.lastUsed", "Last Used")}
                  </TableSortLabel>
                </TableCell>
                <TableCell align="right" sx={{ fontWeight: 600 }}>
                  {t("common.labels.actions")}
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredApiKeys.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} sx={{ p: 0, border: 0 }}>
                    <EmptyTableState
                      message={
                        searchTerm || filterCategory !== "all"
                          ? t("apiKeys.emptyState.noMatchingApiKeys")
                          : t("apiKeys.emptyState.noApiKeys")
                      }
                      icon={<VpnKeyIcon sx={{ fontSize: 40 }} />}
                      action={
                        !(searchTerm || filterCategory !== "all") ? (
                          <Can I="create" a="api-key">
                            <Button
                              variant="contained"
                              startIcon={<AddIcon />}
                              onClick={handleAddApiKey}
                            >
                              {t("apiKeys.addApiKey")}
                            </Button>
                          </Can>
                        ) : undefined
                      }
                    />
                  </TableCell>
                </TableRow>
              ) : (
                filteredApiKeys.map((apiKey) => (
                  <TableRow
                    key={apiKey.id}
                    hover
                    sx={{
                      cursor: "pointer",
                      opacity: apiKey.isEnabled ? 1 : 0.6,
                      "&:last-child td": { border: 0 },
                    }}
                    onClick={() => handleViewApiKey(apiKey)}
                  >
                    {/* Name + description */}
                    <TableCell>
                      <Box display="flex" alignItems="center" gap={1}>
                        <VpnKeyIcon
                          sx={{
                            fontSize: 18,
                            color: apiKey.isEnabled ? "primary.main" : "text.disabled",
                            flexShrink: 0,
                          }}
                        />
                        <Box sx={{ minWidth: 0 }}>
                          <Typography
                            variant="body2"
                            sx={{
                              fontWeight: 600,
                              overflow: "hidden",
                              textOverflow: "ellipsis",
                              whiteSpace: "nowrap",
                            }}
                          >
                            {apiKey.name}
                          </Typography>
                          {apiKey.description && (
                            <Typography
                              variant="caption"
                              color="text.secondary"
                              sx={{
                                display: "block",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                                maxWidth: 220,
                              }}
                            >
                              {apiKey.description}
                            </Typography>
                          )}
                        </Box>
                      </Box>
                    </TableCell>

                    {/* Status */}
                    <TableCell>
                      <Chip
                        label={
                          apiKey.isEnabled
                            ? t("common.labels.enabled")
                            : t("common.labels.disabled")
                        }
                        size="small"
                        color={apiKey.isEnabled ? "success" : "default"}
                        variant="outlined"
                        sx={{ fontWeight: 500 }}
                      />
                    </TableCell>

                    {/* Scope */}
                    <TableCell>
                      {apiKey.scope ? (
                        <Chip
                          label={apiKey.scope}
                          size="small"
                          variant="outlined"
                          color={
                            apiKey.scope === "admin"
                              ? "error"
                              : apiKey.scope === "read-write"
                                ? "primary"
                                : "default"
                          }
                          sx={{ textTransform: "capitalize" }}
                        />
                      ) : (
                        <Typography variant="body2" color="text.disabled">
                          —
                        </Typography>
                      )}
                    </TableCell>

                    {/* Created */}
                    <TableCell>
                      <Tooltip title={formatLocalDateTime(apiKey.createdAt)} arrow>
                        <Typography variant="body2" color="text.secondary">
                          {formatRelativeTime(apiKey.createdAt)}
                        </Typography>
                      </Tooltip>
                    </TableCell>

                    {/* Last Used */}
                    <TableCell>
                      {apiKey.lastUsed ? (
                        <Tooltip title={formatLocalDateTime(apiKey.lastUsed)} arrow>
                          <Typography variant="body2" color="text.secondary">
                            {formatRelativeTime(apiKey.lastUsed)}
                          </Typography>
                        </Tooltip>
                      ) : (
                        <Typography variant="body2" color="text.disabled">
                          {t("common.labels.never", "Never")}
                        </Typography>
                      )}
                    </TableCell>

                    {/* Actions */}
                    <TableCell align="right" onClick={(e) => e.stopPropagation()}>
                      <Box display="flex" justifyContent="flex-end" gap={0.5}>
                        <Can I="view" a="api-key">
                          <Tooltip title={t("common.actions.viewDetails")}>
                            <IconButton
                              size="small"
                              onClick={() => handleViewApiKey(apiKey)}
                              aria-label={t("common.actions.viewDetails")}
                            >
                              <VisibilityIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </Can>
                        <Can I="edit" a="api-key">
                          <Tooltip title={t("common.editApiKey")}>
                            <IconButton
                              size="small"
                              onClick={() => handleEditApiKey(apiKey)}
                              aria-label={t("common.editApiKey")}
                              sx={{ color: "info.main" }}
                            >
                              <EditIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </Can>
                        <Can I="delete" a="api-key">
                          <Tooltip title={t("common.deleteApiKey")}>
                            <IconButton
                              size="small"
                              onClick={() => handleDeleteApiKey(apiKey)}
                              aria-label={t("common.deleteApiKey")}
                              sx={{ color: "error.main" }}
                            >
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </Can>
                      </Box>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Dialogs */}
      <ApiKeyFormDialog
        open={isFormDialogOpen}
        onClose={handleFormDialogClose}
        onSuccess={handleFormDialogSuccess}
        apiKey={isEditMode ? selectedApiKey : null}
        isEditMode={isEditMode}
      />
      <DeleteApiKeyDialog
        open={isDeleteDialogOpen}
        onClose={handleDeleteDialogClose}
        onSuccess={handleDeleteDialogSuccess}
        apiKey={selectedApiKey}
      />
      <ApiKeyDetailsDialog
        open={isDetailsDialogOpen}
        onClose={handleDetailsDialogClose}
        onEdit={handleDetailsDialogEdit}
        apiKey={selectedApiKey}
      />

      <Snackbar
        open={snackbarOpen}
        autoHideDuration={6000}
        onClose={handleSnackbarClose}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
      >
        <Alert onClose={handleSnackbarClose} severity={snackbarSeverity} sx={{ width: "100%" }}>
          {snackbarMessage}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default ApiKeyManagement;
