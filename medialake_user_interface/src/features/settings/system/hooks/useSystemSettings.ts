import { useState, useEffect } from 'react';
import { 
  useSearchProvider, 
  useCreateSearchProvider, 
  useUpdateSearchProvider 
} from '../api/systemHooks';
import { 
  SearchProvider, 
} from '../types/system.types';
import { SYSTEM_SETTINGS_CONFIG } from '../config';

// Function to check if semantic search is properly configured and enabled
export const useSemanticSearchStatus = () => {
  const { data: providerData, isLoading, error } = useSearchProvider();
  
  const isSemanticSearchEnabled = !!providerData?.data?.searchProvider?.isEnabled && 
                                !!providerData?.data?.searchProvider?.isConfigured;
  
  const isConfigured = !!providerData?.data?.searchProvider?.isConfigured;
  
  return {
    isSemanticSearchEnabled,
    isConfigured,
    isLoading,
    error,
    providerData
  };
};

export const useSystemSettingsManager = () => {
  const [provider, setProvider] = useState<SearchProvider>({
    id: '',
    name: SYSTEM_SETTINGS_CONFIG.PROVIDERS.TWELVE_LABS.name,
    type: SYSTEM_SETTINGS_CONFIG.PROVIDERS.TWELVE_LABS.type,
    apiKey: '',
    endpoint: SYSTEM_SETTINGS_CONFIG.PROVIDERS.TWELVE_LABS.defaultEndpoint,
    isConfigured: false,
    isEnabled: true
  });
  
  const [isProviderDialogOpen, setIsProviderDialogOpen] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [newProviderDetails, setNewProviderDetails] = useState<Partial<SearchProvider>>({
    apiKey: '',
    endpoint: SYSTEM_SETTINGS_CONFIG.PROVIDERS.TWELVE_LABS.defaultEndpoint
  });

  // Fetch the current search provider
  const { 
    data: providerData, 
    isLoading: isProviderLoading, 
    error: providerError 
  } = useSearchProvider();

  // Mutations for creating and updating the provider
  const createProvider = useCreateSearchProvider();
  const updateProvider = useUpdateSearchProvider();

  // Update the provider state when data is fetched
  useEffect(() => {
    if (providerData?.data?.searchProvider) {
      const fetchedProvider = providerData.data.searchProvider;
      setProvider({
        ...fetchedProvider,
        isConfigured: true
      });
    }
  }, [providerData]);

  // Handler for opening the add provider dialog
  const handleAddProviderClick = () => {
    setIsEditMode(false);
    setNewProviderDetails({
      apiKey: '',
      endpoint: SYSTEM_SETTINGS_CONFIG.PROVIDERS.TWELVE_LABS.defaultEndpoint
    });
    setIsProviderDialogOpen(true);
  };

  // Handler for opening the edit provider dialog
  const handleEditProviderClick = () => {
    setIsEditMode(true);
    setNewProviderDetails({
      apiKey: provider.apiKey || '',
      endpoint: provider.endpoint || SYSTEM_SETTINGS_CONFIG.PROVIDERS.TWELVE_LABS.defaultEndpoint
    });
    setIsProviderDialogOpen(true);
  };

  // Handler for closing the dialog
  const handleCloseDialog = () => {
    setIsProviderDialogOpen(false);
  };

  // Handler for text field changes
  const handleTextFieldChange = (field: keyof SearchProvider) => (
    event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    setNewProviderDetails({
      ...newProviderDetails,
      [field]: event.target.value
    });
  };

  // Handler for configuring the provider
  const handleConfigureProvider = async () => {
    if (newProviderDetails.apiKey) {
      try {
        if (isEditMode && provider.id) {
          // Update existing provider
          await updateProvider.mutateAsync({
            apiKey: newProviderDetails.apiKey,
            endpoint: newProviderDetails.endpoint,
            isEnabled: true
          });
        } else {
          // Create new provider
          await createProvider.mutateAsync({
            name: SYSTEM_SETTINGS_CONFIG.PROVIDERS.TWELVE_LABS.name,
            type: SYSTEM_SETTINGS_CONFIG.PROVIDERS.TWELVE_LABS.type,
            apiKey: newProviderDetails.apiKey || '',
            endpoint: newProviderDetails.endpoint,
            isEnabled: true
          });
        }
        
        // Close the dialog after successful operation
        handleCloseDialog();
      } catch (error) {
        console.error('Error configuring provider:', error);
      }
    }
  };

  // Handler for resetting the provider
  const handleResetProvider = async () => {
    if (provider.id) {
      try {
        await updateProvider.mutateAsync({
          apiKey: '',
          isEnabled: false
        });
        
        setProvider({
          ...provider,
          apiKey: '',
          isConfigured: false,
          isEnabled: false
        });
      } catch (error) {
        console.error('Error resetting provider:', error);
      }
    }
  };

  return {
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
    isSubmitting: createProvider.isPending || updateProvider.isPending,
    updateProvider,
    setProvider
  };
}; 