// SystemSettingsPage.tsx

import React, { useState, useEffect } from "react";
import {
  Box,
  Typography,
  Paper,
  Tabs,
  Tab,
  Button,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Divider,
  useTheme,
  Switch,
  CircularProgress,
  Alert,
  Snackbar,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Card,
  CardContent,
  Chip,
  IconButton,
  InputAdornment,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import {
  Edit as EditIcon,
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
} from "@mui/icons-material";
import ApiStatusModal from "@/components/ApiStatusModal";
import { useSemanticSearchSettings } from "@/features/settings/system/hooks/useSystemSettings";
import { SYSTEM_SETTINGS_CONFIG } from "@/features/settings/system/config";
import { ApiKeyManagement } from "@/components/settings/api-keys";
import { UpgradeSection } from "@/components/settings/UpgradeSection";
import { Can } from "@/permissions/components/Can";
import CollectionTypesManagement from "@/components/settings/CollectionTypesManagement";
import { useFeatureFlag } from "@/utils/featureFlags";

// Fallback notification hook
const useNotificationWithFallback = () => {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [severity, setSeverity] = useState<"success" | "info" | "warning" | "error">("info");

  let globalNotification: any = null;
  try {
    // Dynamic import to avoid SSR/client mismatch
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { useNotification } = require("@/shared/context/NotificationContext");
    globalNotification = useNotification();
  } catch {
    console.log("NotificationContext not available, using fallback");
  }

  const showNotification = (
    msg: string,
    sev: "success" | "info" | "warning" | "error" = "info"
  ) => {
    if (globalNotification) {
      globalNotification.showNotification(msg, sev);
    } else {
      setMessage(msg);
      setSeverity(sev);
      setOpen(true);
    }
  };

  const hideNotification = () => {
    setOpen(false);
  };

  return {
    showNotification,
    hideNotification,
    open,
    message,
    severity,
    usingFallback: !globalNotification,
  };
};

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

const TabPanel: React.FC<TabPanelProps> = ({ children, value, index, ...other }) => (
  <div
    role="tabpanel"
    hidden={value !== index}
    id={`settings-tabpanel-${index}`}
    aria-labelledby={`settings-tab-${index}`}
    {...other}
    style={{ width: "100%", height: "100%" }}
  >
    {value === index && <Box sx={{ p: 3, height: "100%" }}>{children}</Box>}
  </div>
);

const SystemSettingsPage: React.FC = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const [tabValue, setTabValue] = useState(0);
  const [showApiKey, setShowApiKey] = useState(false);
  const [apiKeySaveModalState, setApiKeySaveModalState] = useState<{
    open: boolean;
    status: "loading" | "success" | "error";
    action: string;
    message?: string;
  }>({
    open: false,
    status: "loading",
    action: "",
    message: undefined,
  });

  // Feature flags
  const systemUpgradesEnabled = useFeatureFlag("system-upgrades-enabled", false);

  // Notification
  const {
    showNotification,
    hideNotification,
    open: notificationOpen,
    message: notificationMessage,
    severity: notificationSeverity,
    usingFallback,
  } = useNotificationWithFallback();

  // New semantic-search-settings hook
  const {
    settings,
    hasChanges,
    isLoading,
    error,
    isApiKeyDialogOpen,
    apiKeyInput,
    isEditingApiKey,
    handleToggleChange,
    handleProviderTypeChange,
    handleEmbeddingStoreChange,
    handleSaveEmbeddingStore,
    handleOpenApiKeyDialog,
    handleCloseApiKeyDialog,
    handleSaveApiKey,
    handleSave,
    handleCancel,
    isSaving,
    setApiKeyInput,
  } = useSemanticSearchSettings();

  const handleTabChange = (_: React.SyntheticEvent, newVal: number) => {
    setTabValue(newVal);
  };

  const handleSaveSettings = async () => {
    const ok = await handleSave();
    showNotification(
      ok
        ? t("settings.systemSettings.search.saveSuccess", "Settings saved successfully")
        : t("settings.systemSettings.search.saveError", "Failed to save settings"),
      ok ? "success" : "error"
    );
  };

  const handleCancelSettings = () => {
    handleCancel();
    showNotification(
      t("settings.systemSettings.search.cancelSuccess", "Changes cancelled"),
      "info"
    );
  };

  const handleSaveEmbeddingStoreSettings = async () => {
    try {
      await handleSaveEmbeddingStore();
      showNotification(
        t(
          "settings.systemSettings.search.embeddingStoreSaveSuccess",
          "Embedding store settings saved successfully"
        ),
        "success"
      );
    } catch {
      showNotification(
        t(
          "settings.systemSettings.search.embeddingStoreSaveError",
          "Failed to save embedding store settings"
        ),
        "error"
      );
    }
  };

  useEffect(() => {
    if (isApiKeyDialogOpen) {
      setApiKeyInput(settings.provider.config?.apiKey ?? "");
    }
  }, [isApiKeyDialogOpen, settings.provider.config, setApiKeyInput]);

  const onSaveApiKey = async () => {
    // Close the API key dialog and show loading modal
    handleCloseApiKeyDialog();
    setApiKeySaveModalState({
      open: true,
      status: "loading",
      action: t("settings.systemSettings.search.savingApiKey", "Saving API Key"),
      message: t(
        "settings.systemSettings.search.savingApiKeyMessage",
        "Configuring search provider..."
      ),
    });

    try {
      const success = await handleSaveApiKey();
      if (success) {
        // Enable the toggle after successful API key save
        handleToggleChange(true);
        setApiKeySaveModalState({
          open: true,
          status: "success",
          action: t("settings.systemSettings.search.apiKeySaveSuccess", "API Key Saved"),
          message: t(
            "settings.systemSettings.search.apiKeySaveSuccessMessage",
            "Search provider has been configured and enabled successfully."
          ),
        });
      } else {
        setApiKeySaveModalState({
          open: true,
          status: "error",
          action: t("settings.systemSettings.search.apiKeySaveError", "Save Failed"),
          message: t(
            "settings.systemSettings.search.apiKeySaveErrorMessage",
            "Failed to save API key. Please try again."
          ),
        });
      }
    } catch (err) {
      setApiKeySaveModalState({
        open: true,
        status: "error",
        action: t("settings.systemSettings.search.apiKeySaveError", "Save Failed"),
        message: t(
          "settings.systemSettings.search.apiKeySaveErrorMessage",
          "Failed to save API key. Please try again."
        ),
      });
    }
  };

  const handleApiKeySaveModalClose = () => {
    setApiKeySaveModalState({
      open: false,
      status: "loading",
      action: "",
      message: undefined,
    });
    setShowApiKey(false);
  };

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "calc(100vh - 120px)",
        p: 3,
      }}
    >
      {/* Local fallback notification */}
      {usingFallback && (
        <Snackbar
          open={notificationOpen}
          autoHideDuration={4000}
          onClose={hideNotification}
          anchorOrigin={{ vertical: "top", horizontal: "right" }}
        >
          <Alert onClose={hideNotification} severity={notificationSeverity} sx={{ width: "100%" }}>
            {notificationMessage}
          </Alert>
        </Snackbar>
      )}

      <Typography variant="h4" gutterBottom align="center" sx={{ mb: 4 }}>
        {t("settings.systemSettings.title", "System Settings")}
      </Typography>

      <Paper
        elevation={3}
        sx={{
          borderRadius: 2,
          overflow: "hidden",
          display: "flex",
          width: "1350px",
          height: "750px",
          maxWidth: "90vw",
        }}
      >
        <Box
          sx={{
            width: "250px",
            borderRight: `1px solid ${theme.palette.divider}`,
            backgroundColor: theme.palette.background.default,
          }}
        >
          <Tabs
            orientation="vertical"
            variant="scrollable"
            value={tabValue}
            onChange={handleTabChange}
            sx={{
              height: "100%",
              "& .MuiTab-root": {
                alignItems: "flex-start",
                textAlign: "left",
                pl: 3,
              },
            }}
          >
            <Tab label={t("settings.systemSettings.tabs.search", "Search")} />
            <Tab label={t("settings.systemSettings.tabs.apiKeys", "API Keys")} />
            <Tab label={t("settings.systemSettings.tabs.collections", "Collections")} />
            {systemUpgradesEnabled.value && (
              <Tab label={t("settings.systemSettings.tabs.upgrades", "Upgrades")} />
            )}
          </Tabs>
        </Box>

        <Box sx={{ flex: 1, display: "flex", flexDirection: "column" }}>
          <TabPanel value={tabValue} index={0}>
            <Typography variant="h6" gutterBottom>
              {t("settings.systemSettings.search.title", "Search Configuration")}
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              {t(
                "settings.systemSettings.search.description",
                "Configure the search provider for enhanced search capabilities across your media assets."
              )}
            </Typography>
            <Divider sx={{ my: 3 }} />

            {isLoading ? (
              <Box sx={{ display: "flex", justifyContent: "center", my: 4 }}>
                <CircularProgress />
              </Box>
            ) : error ? (
              <Alert severity="error" sx={{ my: 2 }}>
                {t("settings.systemSettings.search.errorLoading", "Error loading settings")}
              </Alert>
            ) : (
              <Box sx={{ display: "flex", flexDirection: "column", gap: 4 }}>
                {/* 1. Semantic Search Enabled */}
                <Card
                  elevation={0}
                  sx={{
                    border: `1px solid ${theme.palette.divider}`,
                    borderRadius: 2,
                  }}
                >
                  <CardContent>
                    <Box
                      sx={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                      }}
                    >
                      <Box>
                        <Typography variant="h6" sx={{ mb: 1 }}>
                          {t(
                            "settings.systemSettings.search.semanticEnabled",
                            "Semantic Search Enabled"
                          )}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {t(
                            "settings.systemSettings.search.semanticEnabledDesc",
                            "Enable or disable semantic search functionality"
                          )}
                        </Typography>
                      </Box>
                      <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
                        <Chip
                          label={settings.isEnabled ? "ON" : "OFF"}
                          color={settings.isEnabled ? "success" : "error"}
                          size="small"
                        />
                        <Switch
                          checked={settings.isEnabled}
                          onChange={(_evt, checked) => handleToggleChange(checked)}
                          disabled={false}
                          color="success"
                          size="medium"
                        />
                      </Box>
                    </Box>
                  </CardContent>
                </Card>

                {/* 2. Semantic Search Provider */}
                <Card
                  elevation={0}
                  sx={{
                    border: `1px solid ${theme.palette.divider}`,
                    borderRadius: 2,
                    opacity: settings.isEnabled ? 1 : 0.5,
                  }}
                >
                  <CardContent>
                    <Typography variant="h6" sx={{ mb: 2 }}>
                      {t("settings.systemSettings.search.provider", "Semantic Search Provider")}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                      {t(
                        "settings.systemSettings.search.providerDesc",
                        "Select the AI provider for semantic search capabilities"
                      )}
                    </Typography>
                    <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
                      <FormControl sx={{ minWidth: 400 }} disabled={!settings.isEnabled}>
                        <InputLabel>
                          {t("settings.systemSettings.search.selectProvider", "Select Provider")}
                        </InputLabel>
                        <Select
                          value={settings.provider.type}
                          label={t(
                            "settings.systemSettings.search.selectProvider",
                            "Select Provider"
                          )}
                          onChange={(e) => handleProviderTypeChange(e.target.value as any)}
                        >
                          <MenuItem value="none">
                            {t(
                              "settings.systemSettings.search.selectProviderOption",
                              "Select a provider..."
                            )}
                          </MenuItem>
                          <MenuItem value="twelvelabs-api">
                            <Box
                              sx={{
                                display: "flex",
                                flexDirection: "column",
                                gap: 0.5,
                              }}
                            >
                              <Box
                                sx={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 1,
                                }}
                              >
                                <Typography>
                                  {SYSTEM_SETTINGS_CONFIG.PROVIDERS.TWELVE_LABS_API.name}
                                </Typography>
                                <Chip
                                  label={t("settings.systemSettings.search.external", "External")}
                                  size="small"
                                  color="success"
                                  sx={{ height: 20, fontSize: "0.7rem" }}
                                />
                              </Box>
                              <Typography variant="caption" color="text.secondary">
                                Supports: Image, Video, Audio
                              </Typography>
                            </Box>
                          </MenuItem>
                          <MenuItem value="twelvelabs-bedrock">
                            <Box
                              sx={{
                                display: "flex",
                                flexDirection: "column",
                                gap: 0.5,
                              }}
                            >
                              <Box
                                sx={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 1,
                                }}
                              >
                                <Typography>
                                  {SYSTEM_SETTINGS_CONFIG.PROVIDERS.TWELVE_LABS_BEDROCK.name}
                                </Typography>
                                <Chip
                                  label={t("settings.systemSettings.search.internal", "Internal")}
                                  size="small"
                                  color="success"
                                  sx={{ height: 20, fontSize: "0.7rem" }}
                                />
                              </Box>
                              <Typography variant="caption" color="text.secondary">
                                Supports: Image, Video, Audio
                              </Typography>
                            </Box>
                          </MenuItem>
                          <MenuItem value="coactive">
                            <Box
                              sx={{
                                display: "flex",
                                flexDirection: "column",
                                gap: 0.5,
                              }}
                            >
                              <Box
                                sx={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 1,
                                }}
                              >
                                <Typography>
                                  {SYSTEM_SETTINGS_CONFIG.PROVIDERS.COACTIVE.name}
                                </Typography>
                                <Chip
                                  label={t("settings.systemSettings.search.external", "External")}
                                  size="small"
                                  color="info"
                                  sx={{ height: 20, fontSize: "0.7rem" }}
                                />
                              </Box>
                              <Typography variant="caption" color="text.secondary">
                                Supports: Image, Video
                              </Typography>
                            </Box>
                          </MenuItem>
                        </Select>
                      </FormControl>
                      {(settings.provider.type === "twelvelabs-api" ||
                        settings.provider.type === "coactive") &&
                        settings.provider.config?.isConfigured && (
                          <Button
                            variant="outlined"
                            startIcon={<EditIcon />}
                            onClick={() => handleOpenApiKeyDialog(true)}
                            disabled={false}
                          >
                            {t("settings.systemSettings.search.editApiKey", "Edit")}
                          </Button>
                        )}
                      {settings.provider.config?.isConfigured && (
                        <Chip
                          icon={<CheckCircleIcon />}
                          label={t("settings.systemSettings.search.configured", "Configured")}
                          color="success"
                          variant="outlined"
                        />
                      )}
                    </Box>
                  </CardContent>
                </Card>

                {/* 3. Semantic Search Embedding Store */}
                <Card
                  elevation={0}
                  sx={{
                    border: `1px solid ${theme.palette.divider}`,
                    borderRadius: 2,
                    opacity: settings.isEnabled && settings.provider.type !== "coactive" ? 1 : 0.5,
                  }}
                >
                  <CardContent>
                    <Typography variant="h6" sx={{ mb: 2 }}>
                      {t(
                        "settings.systemSettings.search.embeddingStore",
                        "Semantic Search Embedding Store"
                      )}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                      {settings.provider.type === "coactive"
                        ? t(
                            "settings.systemSettings.search.embeddingStoreCoactiveDesc",
                            "Coactive AI uses its own external search service and does not require an embedding store configuration."
                          )
                        : t(
                            "settings.systemSettings.search.embeddingStoreDesc",
                            "Choose where to store and search vector embeddings"
                          )}
                    </Typography>

                    {settings.provider.type !== "coactive" ? (
                      <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
                        <FormControl sx={{ minWidth: 200 }} disabled={!settings.isEnabled}>
                          <InputLabel>
                            {t("settings.systemSettings.search.selectStore", "Select Store")}
                          </InputLabel>
                          <Select
                            value={settings.embeddingStore.type}
                            label={t("settings.systemSettings.search.selectStore", "Select Store")}
                            onChange={(e) =>
                              handleEmbeddingStoreChange(
                                e.target.value as "opensearch" | "s3-vector"
                              )
                            }
                          >
                            <MenuItem value="opensearch">
                              {SYSTEM_SETTINGS_CONFIG.EMBEDDING_STORES.OPENSEARCH.name}
                            </MenuItem>
                            <MenuItem value="s3-vector">
                              <Box
                                sx={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 1,
                                }}
                              >
                                <Typography>
                                  {SYSTEM_SETTINGS_CONFIG.EMBEDDING_STORES.S3_VECTOR.name}
                                </Typography>
                                <Chip
                                  label={t("settings.systemSettings.search.preview", "Preview")}
                                  size="small"
                                  color="warning"
                                  sx={{ height: 20, fontSize: "0.7rem" }}
                                />
                              </Box>
                            </MenuItem>
                          </Select>
                        </FormControl>

                        <Button
                          variant="contained"
                          onClick={handleSaveEmbeddingStoreSettings}
                          disabled={!settings.isEnabled || isSaving}
                          startIcon={
                            isSaving ? <CircularProgress size={16} /> : <CheckCircleIcon />
                          }
                        >
                          {isSaving ? t("common.saving", "Saving...") : t("common.save", "Save")}
                        </Button>
                      </Box>
                    ) : (
                      <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
                        <Chip
                          label={t(
                            "settings.systemSettings.search.externalService",
                            "External Service"
                          )}
                          color="info"
                          variant="outlined"
                        />
                      </Box>
                    )}
                  </CardContent>
                </Card>

                {/* Save & Cancel */}
                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "flex-end",
                    gap: 2,
                    mt: 4,
                    pt: 3,
                    borderTop: `1px solid ${theme.palette.divider}`,
                  }}
                >
                  <Button
                    variant="outlined"
                    onClick={handleCancelSettings}
                    disabled={!hasChanges || isSaving}
                    startIcon={<CancelIcon />}
                  >
                    {t("common.cancel", "Cancel")}
                  </Button>
                  <Button
                    variant="contained"
                    onClick={handleSaveSettings}
                    disabled={!hasChanges || isSaving}
                    startIcon={isSaving ? <CircularProgress size={20} /> : <CheckCircleIcon />}
                  >
                    {isSaving ? t("common.saving", "Saving...") : t("common.save", "Save")}
                  </Button>
                </Box>
              </Box>
            )}
          </TabPanel>

          <TabPanel value={tabValue} index={1}>
            <Can I="view" a="api-key">
              <ApiKeyManagement />
            </Can>
            <Can I="view" a="api-key">
              {(allowed) =>
                !allowed && (
                  <Box
                    sx={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      justifyContent: "center",
                      height: "100%",
                      textAlign: "center",
                      py: 8,
                    }}
                  >
                    <Typography variant="h6" color="text.secondary" gutterBottom>
                      {t("permissions.accessDenied", "Access Denied")}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {t(
                        "permissions.apiKeyAccessDenied",
                        "You don't have permission to view API keys."
                      )}
                    </Typography>
                  </Box>
                )
              }
            </Can>
          </TabPanel>

          <TabPanel value={tabValue} index={2}>
            <Can I="manage" a="collection-types">
              <CollectionTypesManagement />
            </Can>
            <Can I="manage" a="collection-types">
              {(allowed) =>
                !allowed && (
                  <Box
                    sx={{
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      justifyContent: "center",
                      height: "100%",
                      textAlign: "center",
                      py: 8,
                    }}
                  >
                    <Typography variant="h6" color="text.secondary" gutterBottom>
                      {t("permissions.accessDenied", "Access Denied")}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {t(
                        "permissions.collectionTypesAccessDenied",
                        "You don't have permission to manage collection types."
                      )}
                    </Typography>
                  </Box>
                )
              }
            </Can>
          </TabPanel>
          {systemUpgradesEnabled.value && (
            <TabPanel value={tabValue} index={2}>
              {/* Temporarily removed permission check for debugging */}
              <UpgradeSection />
            </TabPanel>
          )}
        </Box>
      </Paper>

      {/* API Key Configuration Dialog */}
      <Dialog open={isApiKeyDialogOpen} onClose={handleCloseApiKeyDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {isEditingApiKey
            ? t("settings.systemSettings.search.editApiKey", "Edit API Key")
            : t("settings.systemSettings.search.configureApiKey", "Configure API Key")}
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t(
              "settings.systemSettings.search.apiKeyDesc",
              "Enter your TwelveLabs API key to enable semantic search functionality."
            )}
          </Typography>
          <TextField
            label={t("settings.systemSettings.search.apiKey", "API Key")}
            value={apiKeyInput}
            onChange={(e) => setApiKeyInput(e.target.value)}
            fullWidth
            margin="normal"
            type={showApiKey ? "text" : "password"}
            placeholder={t("common.placeholders.enterApiKey")}
            required
            autoFocus
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    aria-label={showApiKey ? "Hide API key" : "Show API key"}
                    onClick={() => setShowApiKey(!showApiKey)}
                    edge="end"
                  >
                    {showApiKey ? <VisibilityOffIcon /> : <VisibilityIcon />}
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseApiKeyDialog}>{t("common.cancel", "Cancel")}</Button>
          <Button
            onClick={onSaveApiKey}
            variant="contained"
            color="primary"
            disabled={!apiKeyInput}
          >
            {t("common.save", "Save")}
          </Button>
        </DialogActions>
      </Dialog>

      {/* API Key Save Status Modal */}
      <ApiStatusModal
        open={apiKeySaveModalState.open}
        onClose={handleApiKeySaveModalClose}
        status={apiKeySaveModalState.status}
        action={apiKeySaveModalState.action}
        message={apiKeySaveModalState.message}
      />
    </Box>
  );
};

export default SystemSettingsPage;
