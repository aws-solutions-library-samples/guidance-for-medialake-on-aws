import React, { useState, useMemo } from "react";
import {
  Box,
  Button,
  Typography,
  Grid,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  CircularProgress,
  Alert,
  IconButton,
  InputAdornment,
  Snackbar,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import SearchIcon from "@mui/icons-material/Search";
import FilterListIcon from "@mui/icons-material/FilterList";
import { useTranslation } from "react-i18next";
import { PageHeader, PageContent } from "@/components/common/layout";
import { Can } from "@/permissions/components/Can";
import { useGetApiKeys } from "@/api/hooks/useApiKeys";
import { useErrorModal } from "@/hooks/useErrorModal";
import { ApiKey } from "@/api/types/apiKey.types";
import ApiKeyCard from "./ApiKeyCard";
import ApiKeyFormDialog from "./ApiKeyFormDialog";
import DeleteApiKeyDialog from "./DeleteApiKeyDialog";
import ApiKeyDetailsDialog from "./ApiKeyDetailsDialog";

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
  const [snackbarSeverity, setSnackbarSeverity] = useState<"success" | "error">(
    "success",
  );

  const { showError } = useErrorModal();

  // Fetch API keys
  const { data: apiKeys = [], isLoading, error } = useGetApiKeys(true);

  // Filter API keys based on search term and category
  const filteredApiKeys = useMemo(() => {
    let filtered = apiKeys;

    // Filter by search term
    if (searchTerm) {
      filtered = filtered.filter(
        (apiKey) =>
          apiKey.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
          apiKey.description.toLowerCase().includes(searchTerm.toLowerCase()),
      );
    }

    // Filter by category
    if (filterCategory !== "all") {
      filtered = filtered.filter((apiKey) => {
        if (filterCategory === "enabled") return apiKey.isEnabled;
        if (filterCategory === "disabled") return !apiKey.isEnabled;
        return true;
      });
    }

    return filtered;
  }, [apiKeys, searchTerm, filterCategory]);

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

  // Show error if there's an API error
  if (error) {
    showError(`Failed to fetch API keys: ${error.message}`);
  }

  return (
    <Box>
      <PageHeader
        title="API Key Management"
        description="Manage API keys for programmatic access to the system"
        action={
          <Can I="create" a="api-key">
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={handleAddApiKey}
            >
              Add API Key
            </Button>
          </Can>
        }
      />

      <PageContent>
        {/* Search and Filter Bar */}
        <Box sx={{ mb: 3, overflow: "visible" }}>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={6}>
              <TextField
                fullWidth
                placeholder="Search API keys..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                InputProps={{
                  startAdornment: (
                    <InputAdornment position="start">
                      <SearchIcon />
                    </InputAdornment>
                  ),
                }}
              />
            </Grid>
            <Grid item xs={12} md={3}>
              <FormControl fullWidth sx={{ overflow: "visible" }}>
                <InputLabel
                  shrink
                  sx={{ backgroundColor: "background.paper", px: 0.5 }}
                >
                  Category
                </InputLabel>
                <Select
                  value={filterCategory}
                  label="Category"
                  onChange={(e) => setFilterCategory(e.target.value)}
                  startAdornment={
                    <InputAdornment position="start">
                      <FilterListIcon />
                    </InputAdornment>
                  }
                  notched
                >
                  <MenuItem value="all">All API Keys</MenuItem>
                  <MenuItem value="enabled">Enabled</MenuItem>
                  <MenuItem value="disabled">Disabled</MenuItem>
                </Select>
              </FormControl>
            </Grid>
          </Grid>
        </Box>

        {/* Loading State */}
        {isLoading && (
          <Box display="flex" justifyContent="center" py={4}>
            <CircularProgress />
          </Box>
        )}

        {/* Error State */}
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            Failed to load API keys. Please try again.
          </Alert>
        )}

        {/* Empty State */}
        {!isLoading && !error && filteredApiKeys.length === 0 && (
          <Box
            display="flex"
            flexDirection="column"
            alignItems="center"
            justifyContent="center"
            py={8}
          >
            <Typography variant="h6" color="textSecondary" gutterBottom>
              {searchTerm || filterCategory !== "all"
                ? "No API keys match your search"
                : "No API keys found"}
            </Typography>
            <Typography variant="body2" color="textSecondary" sx={{ mb: 3 }}>
              {searchTerm || filterCategory !== "all"
                ? "Try adjusting your search or filter criteria"
                : "Create your first API key to get started"}
            </Typography>
            <Can I="create" a="api-key">
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={handleAddApiKey}
              >
                Add API Key
              </Button>
            </Can>
          </Box>
        )}

        {/* API Keys Grid */}
        {!isLoading && !error && filteredApiKeys.length > 0 && (
          <Grid container spacing={3}>
            {filteredApiKeys.map((apiKey) => (
              <Grid item xs={12} sm={6} md={4} key={apiKey.id}>
                <ApiKeyCard
                  apiKey={apiKey}
                  onView={handleViewApiKey}
                  onEdit={handleEditApiKey}
                  onDelete={handleDeleteApiKey}
                />
              </Grid>
            ))}
          </Grid>
        )}
      </PageContent>

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

      {/* Snackbar for notifications */}
      <Snackbar
        open={snackbarOpen}
        autoHideDuration={6000}
        onClose={handleSnackbarClose}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
      >
        <Alert
          onClose={handleSnackbarClose}
          severity={snackbarSeverity}
          sx={{ width: "100%" }}
        >
          {snackbarMessage}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default ApiKeyManagement;
