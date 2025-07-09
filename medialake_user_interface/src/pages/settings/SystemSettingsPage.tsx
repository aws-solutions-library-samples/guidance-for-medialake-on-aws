import React, { useState, useEffect } from 'react';
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
  Snackbar
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { Add as AddIcon, Edit as EditIcon } from '@mui/icons-material';
import { useSystemSettingsManager, useSemanticSearchStatus } from '@/features/settings/system/hooks/useSystemSettings';

// Create a custom hook that falls back to a local notification if the global one isn't available
const useNotificationWithFallback = () => {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState('');
  const [severity, setSeverity] = useState<'success' | 'info' | 'warning' | 'error'>('info');
  
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
  
  const showNotification = (msg: string, sev: 'success' | 'info' | 'warning' | 'error' = 'info') => {
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
    usingFallback: !globalNotification
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
      {value === index && (
        <Box sx={{ p: 3, height: '100%' }}>
          {children}
        </Box>
      )}
    </div>
  );
}

const SystemSettingsPage: React.FC = () => {
  const { t } = useTranslation();
  const theme = useTheme();
  const [tabValue, setTabValue] = useState(0);
  const { 
    showNotification, 
    hideNotification, 
    open: notificationOpen, 
    message: notificationMessage, 
    severity: notificationSeverity,
    usingFallback 
  } = useNotificationWithFallback();
  
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
    setProvider
  } = useSystemSettingsManager();

  // Initialize provider data on mount
  useEffect(() => {
    if (!isProviderLoading && !providerError && semanticSearchStatus.providerData?.data?.searchProvider) {
      // If we have fresh data from the semantic search status, update the provider state
      const freshProvider = semanticSearchStatus.providerData.data.searchProvider;
      setProvider({
        ...freshProvider,
        isConfigured: true
      });
    }
  }, [semanticSearchStatus.providerData, isProviderLoading, providerError, setProvider]);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  // Add a handler for the semantic search toggle
  const handleSearchToggleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const isEnabled = event.target.checked;
    
    // If trying to enable search but provider not configured, show warning
    if (isEnabled && !provider.isConfigured) {
      showNotification(
        t('settings.systemSettings.search.providerRequired', 
          'A semantic search provider must be configured before enabling search.'),
        'warning'
      );
      return;
    }
    
    // Update the provider with the new isEnabled value
    if (provider.isConfigured) {
      updateProvider.mutateAsync({
        isEnabled: isEnabled
      });
      
      // Update local state
      setProvider({
        ...provider,
        isEnabled: isEnabled
      });
    }
  };

  return (
    <Box sx={{ 
      display: 'flex', 
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: 'calc(100vh - 120px)',
      p: 3
    }}>
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
        <Box sx={{ 
          width: '250px', 
          borderRight: `1px solid ${theme.palette.divider}`,
          backgroundColor: theme.palette.background.default
        }}>
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
                pl: 3
              }
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
              {t('settings.systemSettings.search.description', 
                'Configure the search provider for enhanced search capabilities across your media assets.')}
            </Typography>
            
            <Divider sx={{ my: 3 }} />
            
            {isProviderLoading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', my: 4 }}>
                <CircularProgress />
              </Box>
            ) : providerError ? (
              <Alert severity="error" sx={{ my: 2 }}>
                {t('settings.systemSettings.search.errorLoading', 'Error loading search provider configuration')}
              </Alert>
            ) : (
              <>
                {/* Semantic Search Enabled Toggle */}
                <Box sx={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center',
                  py: 2,
                  px: 1,
                  borderRadius: 1,
                  mb: 3
                }}>
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
                      <Button
                        variant="outlined"
                        color="secondary"
                        onClick={handleResetProvider}
                      >
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
                  <Box sx={{ 
                    display: 'flex', 
                    flexDirection: 'column', 
                    alignItems: 'center', 
                    justifyContent: 'center',
                    height: '350px',
                    border: `1px dashed ${theme.palette.divider}`,
                    borderRadius: 2,
                    mt: 4
                  }}>
                    <Typography variant="body1" color="text.secondary" align="center">
                      {t('settings.systemSettings.search.noProvider', 
                        'No search provider configured.')}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" align="center" sx={{ mt: 1, mb: 3 }}>
                      {t('settings.systemSettings.search.configurePrompt', 
                        'Configure Twelve Labs to enable search capabilities.')}
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
            )}
          </TabPanel>
        </Box>
      </Paper>
      
      {/* Configure/Edit Provider Dialog */}
      <Dialog open={isProviderDialogOpen} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {isEditMode 
            ? t('settings.systemSettings.search.editProvider', 'Edit Search Provider') 
            : t('settings.systemSettings.search.configureProvider', 'Configure Search Provider')}
        </DialogTitle>
        <DialogContent>
          <TextField
            label={t('settings.systemSettings.search.providerName', 'Provider Name')}
            value={provider.name}
            fullWidth
            margin="normal"
            disabled
          />
          <TextField
            label={t('settings.systemSettings.search.apiKey', 'API Key')}
            value={newProviderDetails.apiKey}
            onChange={handleTextFieldChange('apiKey')}
            fullWidth
            margin="normal"
            type="password"
            required
          />
          <TextField
            label={t('settings.systemSettings.search.endpoint', 'Endpoint URL (Optional)')}
            value={newProviderDetails.endpoint}
            onChange={handleTextFieldChange('endpoint')}
            fullWidth
            margin="normal"
            placeholder="https://api.twelvelabs.io/v1"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog} disabled={isSubmitting}>
            {t('common.cancel', 'Cancel')}
          </Button>
          <Button 
            onClick={handleConfigureProvider} 
            variant="contained" 
            color="primary"
            disabled={!newProviderDetails.apiKey || isSubmitting}
          >
            {isSubmitting ? (
              <CircularProgress size={24} />
            ) : (
              t('common.save', 'Save')
            )}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default SystemSettingsPage; 