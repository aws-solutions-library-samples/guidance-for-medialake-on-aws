import React from 'react';
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
  Grid,
  Divider,
  useTheme,
  Switch,
  FormControlLabel,
  CircularProgress,
  Alert,
  Snackbar,
<<<<<<< HEAD
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { Add as AddIcon, Edit as EditIcon } from '@mui/icons-material';
import {
  useSystemSettingsManager,
  useSemanticSearchStatus,
} from '@/features/settings/system/hooks/useSystemSettings';

// Create a custom hook that falls back to a local notification if the global one isn't available
const useNotificationWithFallback = () => {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState('');
  const [severity, setSeverity] = useState<'success' | 'info' | 'warning' | 'error'>('info');

=======
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Card,
  CardContent,
  Chip
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { Edit as EditIcon, CheckCircle as CheckCircleIcon, Cancel as CancelIcon } from '@mui/icons-material';
import { useSemanticSearchSettings } from '@/features/settings/system/hooks/useSystemSettings';
import { SYSTEM_SETTINGS_CONFIG } from '@/features/settings/system/config';

// Create a custom hook that falls back to a local notification if the global one isn't available
const useNotificationWithFallback = () => {
  const [open, setOpen] = React.useState(false);
  const [message, setMessage] = React.useState('');
  const [severity, setSeverity] = React.useState<'success' | 'info' | 'warning' | 'error'>('info');
  
>>>>>>> feat/s3SearchVectorEmbeddingStore
  // Try to use the global notification context, but don't throw if it's not available
  let globalNotification;
  try {
    // Dynamic import to avoid the error during rendering
    const { useNotification } = require('@/shared/context/NotificationContext');
    globalNotification = useNotification();
  } catch (error) {
    console.log('NotificationContext not available, using fallback');
    globalNotification = null;
  }

  const showNotification = (
    msg: string,
    sev: 'success' | 'info' | 'warning' | 'error' = 'info'
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

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`settings-tabpanel-${index}`}
      aria-labelledby={`settings-tab-${index}`}
      {...other}
      style={{ width: '100%', height: '100%' }}
    >
      {value === index && <Box sx={{ p: 3, height: '100%' }}>{children}</Box>}
    </div>
  );
}

const SystemSettingsPage: React.FC = () => {
  const { t } = useTranslation();
  const theme = useTheme();
<<<<<<< HEAD
  const [tabValue, setTabValue] = useState(0);
  const {
    showNotification,
    hideNotification,
    open: notificationOpen,
    message: notificationMessage,
=======
  const [tabValue, setTabValue] = React.useState(0);
  const { 
    showNotification, 
    hideNotification, 
    open: notificationOpen, 
    message: notificationMessage, 
>>>>>>> feat/s3SearchVectorEmbeddingStore
    severity: notificationSeverity,
    usingFallback,
  } = useNotificationWithFallback();
<<<<<<< HEAD

  // Use our custom hooks for system settings management
  const semanticSearchStatus = useSemanticSearchStatus();
  const {
    provider,
    isProviderLoading,
    providerError,
    isProviderDialogOpen,
    isEditMode,
    newProviderDetails,
    handleAddProviderClick,
    handleEditProviderClick,
    handleCloseDialog,
    handleTextFieldChange,
    handleConfigureProvider,
    handleResetProvider,
    isSubmitting,
    updateProvider,
    setProvider,
  } = useSystemSettingsManager();

  // Initialize provider data on mount
  useEffect(() => {
    if (
      !isProviderLoading &&
      !providerError &&
      semanticSearchStatus.providerData?.data?.searchProvider
    ) {
      // If we have fresh data from the semantic search status, update the provider state
      const freshProvider = semanticSearchStatus.providerData.data.searchProvider;
      setProvider({
        ...freshProvider,
        isConfigured: true,
      });
    }
  }, [semanticSearchStatus.providerData, isProviderLoading, providerError, setProvider]);
=======
  
  // Use the new semantic search settings hook
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
    handleOpenApiKeyDialog,
    handleCloseApiKeyDialog,
    handleSaveApiKey,
    handleSave,
    handleCancel,
    isSaving,
    setApiKeyInput
  } = useSemanticSearchSettings();
>>>>>>> feat/s3SearchVectorEmbeddingStore

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

<<<<<<< HEAD
  // Add a handler for the semantic search toggle
  const handleSearchToggleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const isEnabled = event.target.checked;

    // If trying to enable search but provider not configured, show warning
    if (isEnabled && !provider.isConfigured) {
      showNotification(
        t(
          'settings.systemSettings.search.providerRequired',
          'A semantic search provider must be configured before enabling search.'
        ),
        'warning'
      );
      return;
    }

    // Update the provider with the new isEnabled value
    if (provider.isConfigured) {
      updateProvider.mutateAsync({
        isEnabled: isEnabled,
      });

      // Update local state
      setProvider({
        ...provider,
        isEnabled: isEnabled,
      });
=======
  const handleSaveSettings = async () => {
    const success = await handleSave();
    if (success) {
      showNotification(
        t('settings.systemSettings.search.saveSuccess', 'Settings saved successfully'),
        'success'
      );
    } else {
      showNotification(
        t('settings.systemSettings.search.saveError', 'Failed to save settings'),
        'error'
      );
>>>>>>> feat/s3SearchVectorEmbeddingStore
    }
  };

  const handleCancelSettings = () => {
    handleCancel();
    showNotification(
      t('settings.systemSettings.search.cancelSuccess', 'Changes cancelled'),
      'info'
    );
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: 'calc(100vh - 120px)',
        p: 3,
      }}
    >
      {/* Render fallback notification if using the local version */}
      {usingFallback && (
        <Snackbar
          open={notificationOpen}
          autoHideDuration={4000}
          onClose={hideNotification}
          anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
        >
          <Alert onClose={hideNotification} severity={notificationSeverity} sx={{ width: '100%' }}>
            {notificationMessage}
          </Alert>
        </Snackbar>
      )}

      <Typography variant="h4" gutterBottom align="center" sx={{ mb: 4 }}>
        {t('settings.systemSettings.title', 'System Settings')}
      </Typography>

      <Paper
        elevation={3}
        sx={{
          borderRadius: 2,
          overflow: 'hidden',
          display: 'flex',
          width: '1350px',
          height: '750px',
          maxWidth: '90vw',
        }}
      >
        <Box
          sx={{
            width: '250px',
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
              borderRight: 1,
              borderColor: 'divider',
              height: '100%',
              '& .MuiTab-root': {
                alignItems: 'flex-start',
                textAlign: 'left',
                pl: 3,
              },
            }}
          >
            <Tab label={t('settings.systemSettings.tabs.search', 'Search')} />
          </Tabs>
        </Box>

        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
          <TabPanel value={tabValue} index={0}>
            <Typography variant="h6" gutterBottom>
              {t('settings.systemSettings.search.title', 'Search Configuration')}
            </Typography>
            <Typography variant="body2" color="text.secondary" paragraph>
              {t(
                'settings.systemSettings.search.description',
                'Configure the search provider for enhanced search capabilities across your media assets.'
              )}
            </Typography>

            <Divider sx={{ my: 3 }} />
<<<<<<< HEAD

            {isProviderLoading ? (
=======
            
            {isLoading ? (
>>>>>>> feat/s3SearchVectorEmbeddingStore
              <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
                <CircularProgress />
              </Box>
            ) : error ? (
              <Alert severity="error" sx={{ my: 2 }}>
                {t(
                  'settings.systemSettings.search.errorLoading',
                  'Error loading search provider configuration'
                )}
              </Alert>
            ) : (
<<<<<<< HEAD
              <>
                {/* Semantic Search Enabled Toggle */}
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    py: 2,
                    px: 1,
                    borderRadius: 1,
                    mb: 3,
                  }}
                >
                  <Typography variant="subtitle1">
                    {t('settings.systemSettings.search.semanticEnabled', 'Semantic Search Enabled')}
                  </Typography>
                  <Switch
                    checked={provider.isEnabled || false}
                    onChange={handleSearchToggleChange}
                    disabled={!provider.isConfigured}
                    color="primary"
                  />
                </Box>

                <Divider sx={{ my: 3 }} />

                {/* Search Provider section */}
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
                  <Typography variant="subtitle1" sx={{ mr: 2 }}>
                    {t('settings.systemSettings.search.provider', 'Search Provider:')}
                  </Typography>
                  <Typography variant="body1" sx={{ fontWeight: 500 }}>
                    {provider.name}
                  </Typography>
                  <Box sx={{ flex: 1 }} />
                  {!provider.isConfigured ? (
                    <Button
                      variant="contained"
                      color="primary"
                      startIcon={<AddIcon />}
                      onClick={handleAddProviderClick}
                    >
                      {t('settings.systemSettings.search.configureProvider', 'Configure Provider')}
                    </Button>
                  ) : (
                    <Box sx={{ display: 'flex', gap: 2 }}>
                      <Button
                        variant="outlined"
                        color="primary"
                        startIcon={<EditIcon />}
                        onClick={handleEditProviderClick}
                      >
                        {t('settings.systemSettings.search.editProvider', 'Edit Provider')}
                      </Button>
                      <Button variant="outlined" color="secondary" onClick={handleResetProvider}>
                        {t('settings.systemSettings.search.resetProvider', 'Reset Provider')}
                      </Button>
                    </Box>
                  )}
                </Box>

                {provider.isConfigured && (
                  <Box sx={{ mt: 4 }}>
                    <Typography variant="h6" gutterBottom>
                      {t('settings.systemSettings.search.providerDetails', 'Provider Details')}
                    </Typography>
                    <Grid container spacing={3}>
                      <Grid item xs={12} md={6}>
                        <TextField
                          label={t('settings.systemSettings.search.providerName', 'Provider Name')}
                          value={provider.name}
                          fullWidth
                          disabled
                          margin="normal"
                        />
                      </Grid>
                      <Grid item xs={12}>
                        <TextField
                          label={t('settings.systemSettings.search.apiKey', 'API Key')}
                          value="••••••••••••••••••••••••••••••"
                          fullWidth
                          type="password"
                          disabled
                          margin="normal"
                        />
                      </Grid>
                      {provider.endpoint && (
                        <Grid item xs={12}>
                          <TextField
                            label={t('settings.systemSettings.search.endpoint', 'Endpoint URL')}
                            value={provider.endpoint}
                            fullWidth
                            disabled
                            margin="normal"
                          />
                        </Grid>
                      )}
                    </Grid>
                  </Box>
                )}

                {!provider.isConfigured && (
                  <Box
                    sx={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      height: '350px',
                      border: `1px dashed ${theme.palette.divider}`,
                      borderRadius: 2,
                      mt: 4,
                    }}
                  >
                    <Typography variant="body1" color="text.secondary" align="center">
                      {t(
                        'settings.systemSettings.search.noProvider',
                        'No search provider configured.'
                      )}
                    </Typography>
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      align="center"
                      sx={{ mt: 1, mb: 3 }}
                    >
                      {t(
                        'settings.systemSettings.search.configurePrompt',
                        'Configure Twelve Labs to enable search capabilities.'
                      )}
                    </Typography>
                    <Button
                      variant="contained"
                      color="primary"
                      startIcon={<AddIcon />}
                      onClick={handleAddProviderClick}
                    >
                      {t('settings.systemSettings.search.configureProvider', 'Configure Provider')}
                    </Button>
                  </Box>
                )}
              </>
=======
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {/* Part 1: Semantic Search Enabled Toggle */}
                <Card elevation={0} sx={{ border: `1px solid ${theme.palette.divider}`, borderRadius: 2 }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <Box>
                        <Typography variant="h6" sx={{ mb: 1 }}>
                          {t('settings.systemSettings.search.semanticEnabled', 'Semantic Search Enabled')}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                          {t('settings.systemSettings.search.semanticEnabledDesc', 'Enable or disable semantic search functionality')}
                        </Typography>
                      </Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Chip 
                          label={settings.isEnabled ? 'ON' : 'OFF'} 
                          color={settings.isEnabled ? 'success' : 'error'}
                          variant="filled"
                          size="small"
                        />
                        <Switch
                          checked={settings.isEnabled}
                          onChange={(e) => handleToggleChange(e.target.checked)}
                          color="success"
                          size="medium"
                        />
                      </Box>
                    </Box>
                  </CardContent>
                </Card>

                {/* Part 2: Semantic Search Provider */}
                <Card elevation={0} sx={{ 
                  border: `1px solid ${theme.palette.divider}`, 
                  borderRadius: 2,
                  opacity: settings.isEnabled ? 1 : 0.5
                }}>
                  <CardContent>
                    <Typography variant="h6" sx={{ mb: 2 }}>
                      {t('settings.systemSettings.search.provider', 'Semantic Search Provider')}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                      {t('settings.systemSettings.search.providerDesc', 'Select the AI provider for semantic search capabilities')}
                    </Typography>
                    
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                      <FormControl sx={{ minWidth: 200 }} disabled={!settings.isEnabled}>
                        <InputLabel>{t('settings.systemSettings.search.selectProvider', 'Select Provider')}</InputLabel>
                        <Select
                          value={settings.provider.type}
                          label="Select Provider"
                          onChange={(e) => handleProviderTypeChange(e.target.value as 'twelvelabs-api' | 'twelvelabs-bedrock')}
                        >
                          <MenuItem value="twelvelabs-api">
                            {SYSTEM_SETTINGS_CONFIG.PROVIDERS.TWELVE_LABS_API.name}
                          </MenuItem>
                          <MenuItem value="twelvelabs-bedrock">
                            {SYSTEM_SETTINGS_CONFIG.PROVIDERS.TWELVE_LABS_BEDROCK.name}
                          </MenuItem>
                        </Select>
                      </FormControl>
                      
                      {settings.provider.type === 'twelvelabs-api' && settings.provider.config?.isConfigured && (
                        <Button
                          variant="outlined"
                          startIcon={<EditIcon />}
                          onClick={() => handleOpenApiKeyDialog(true)}
                          disabled={!settings.isEnabled}
                        >
                          {t('settings.systemSettings.search.editApiKey', 'Edit')}
                        </Button>
                      )}
                      
                      {settings.provider.config?.isConfigured && (
                        <Chip
                          icon={<CheckCircleIcon />}
                          label={t('settings.systemSettings.search.configured', 'Configured')}
                          color="success"
                          variant="outlined"
                        />
                      )}
                    </Box>
                  </CardContent>
                </Card>

                {/* Part 3: Semantic Search Embedding Store */}
                <Card elevation={0} sx={{ 
                  border: `1px solid ${theme.palette.divider}`, 
                  borderRadius: 2,
                  opacity: settings.isEnabled ? 1 : 0.5
                }}>
                  <CardContent>
                    <Typography variant="h6" sx={{ mb: 2 }}>
                      {t('settings.systemSettings.search.embeddingStore', 'Semantic Search Embedding Store')}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                      {t('settings.systemSettings.search.embeddingStoreDesc', 'Choose where to store and search vector embeddings')}
                    </Typography>
                    
                    <FormControl sx={{ minWidth: 200 }} disabled={!settings.isEnabled}>
                      <InputLabel>{t('settings.systemSettings.search.selectStore', 'Select Store')}</InputLabel>
                      <Select
                        value={settings.embeddingStore.type}
                        label="Select Store"
                        onChange={(e) => handleEmbeddingStoreChange(e.target.value as 'opensearch' | 's3-vector')}
                      >
                        <MenuItem value="opensearch">
                          {SYSTEM_SETTINGS_CONFIG.EMBEDDING_STORES.OPENSEARCH.name}
                        </MenuItem>
                        <MenuItem value="s3-vector">
                          {SYSTEM_SETTINGS_CONFIG.EMBEDDING_STORES.S3_VECTOR.name}
                        </MenuItem>
                      </Select>
                    </FormControl>
                  </CardContent>
                </Card>

                {/* Save and Cancel Buttons */}
                <Box sx={{ 
                  display: 'flex', 
                  justifyContent: 'flex-end', 
                  gap: 2, 
                  mt: 4, 
                  pt: 3, 
                  borderTop: `1px solid ${theme.palette.divider}` 
                }}>
                  <Button
                    variant="outlined"
                    onClick={handleCancelSettings}
                    disabled={!hasChanges || isSaving}
                    startIcon={<CancelIcon />}
                  >
                    {t('common.cancel', 'Cancel')}
                  </Button>
                  <Button
                    variant="contained"
                    onClick={handleSaveSettings}
                    disabled={!hasChanges || isSaving}
                    startIcon={isSaving ? <CircularProgress size={20} /> : <CheckCircleIcon />}
                  >
                    {isSaving ? t('common.saving', 'Saving...') : t('common.save', 'Save')}
                  </Button>
                </Box>
              </Box>
>>>>>>> feat/s3SearchVectorEmbeddingStore
            )}
          </TabPanel>
        </Box>
      </Paper>
<<<<<<< HEAD

      {/* Configure/Edit Provider Dialog */}
      <Dialog open={isProviderDialogOpen} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {isEditMode
            ? t('settings.systemSettings.search.editProvider', 'Edit Search Provider')
            : t('settings.systemSettings.search.configureProvider', 'Configure Search Provider')}
=======
      
      {/* API Key Configuration Dialog */}
      <Dialog open={isApiKeyDialogOpen} onClose={handleCloseApiKeyDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {isEditingApiKey 
            ? t('settings.systemSettings.search.editApiKey', 'Edit API Key') 
            : t('settings.systemSettings.search.configureApiKey', 'Configure API Key')}
>>>>>>> feat/s3SearchVectorEmbeddingStore
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t('settings.systemSettings.search.apiKeyDesc', 
              'Enter your Twelve Labs API key to enable semantic search functionality.')}
          </Typography>
          <TextField
            label={t('settings.systemSettings.search.apiKey', 'API Key')}
            value={apiKeyInput}
            onChange={(e) => setApiKeyInput(e.target.value)}
            fullWidth
            margin="normal"
            type={isEditingApiKey && apiKeyInput === '••••••••••••••••' ? 'password' : 'text'}
            required
            placeholder="Enter your API key"
            autoFocus
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseApiKeyDialog}>
            {t('common.cancel', 'Cancel')}
          </Button>
<<<<<<< HEAD
          <Button
            onClick={handleConfigureProvider}
            variant="contained"
=======
          <Button 
            onClick={handleSaveApiKey} 
            variant="contained" 
>>>>>>> feat/s3SearchVectorEmbeddingStore
            color="primary"
            disabled={!apiKeyInput || apiKeyInput === '••••••••••••••••'}
          >
<<<<<<< HEAD
            {isSubmitting ? <CircularProgress size={24} /> : t('common.save', 'Save')}
=======
            {t('common.save', 'Save')}
>>>>>>> feat/s3SearchVectorEmbeddingStore
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default SystemSettingsPage;
