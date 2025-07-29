import { useState, useEffect } from "react";
import {
  useSearchProvider,
  useCreateSearchProvider,
  useUpdateSearchProvider,
} from "../api/systemHooks";
import {
  SearchProvider,
  SemanticSearchSettings,
  SystemSettingsState,
} from "../types/system.types";
import { SYSTEM_SETTINGS_CONFIG } from "../config";

// Function to check if semantic search is properly configured and enabled
export const useSemanticSearchStatus = () => {
  const { data: providerData, isLoading, error } = useSearchProvider();

  const isSemanticSearchEnabled =
    !!providerData?.data?.searchProvider?.isEnabled &&
    !!providerData?.data?.searchProvider?.isConfigured;

  const isConfigured = !!providerData?.data?.searchProvider?.isConfigured;

  return {
    isSemanticSearchEnabled,
    isConfigured,
    isLoading,
    error,
    providerData,
  };
};

// New hook for managing the three-part settings
export const useSemanticSearchSettings = () => {
  const [settings, setSettings] = useState<SystemSettingsState>({
    current: {
      isEnabled: false,
      provider: {
        type: "twelvelabs-api",
        config: null,
      },
      embeddingStore: {
        type: "opensearch",
      },
    },
    original: {
      isEnabled: false,
      provider: {
        type: "twelvelabs-api",
        config: null,
      },
      embeddingStore: {
        type: "opensearch",
      },
    },
    hasChanges: false,
  });

  const [isApiKeyDialogOpen, setIsApiKeyDialogOpen] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [isEditingApiKey, setIsEditingApiKey] = useState(false);

  // Fetch the current search provider
  const {
    data: providerData,
    isLoading: isProviderLoading,
    error: providerError,
  } = useSearchProvider();

  // Mutations for creating and updating the provider
  const createProvider = useCreateSearchProvider();
  const updateProvider = useUpdateSearchProvider();

  // Initialize settings from fetched data
  useEffect(() => {
    if (providerData?.data?.searchProvider) {
      const fetchedProvider = providerData.data.searchProvider;
      const fetchedEmbeddingStore = providerData.data.embeddingStore;
      const providerType =
        fetchedProvider.type === "twelvelabs-bedrock"
          ? "twelvelabs-bedrock"
          : "twelvelabs-api";

      const initialSettings: SemanticSearchSettings = {
        isEnabled: fetchedProvider.isEnabled || false,
        provider: {
          type: providerType,
          config: {
            ...fetchedProvider,
            isConfigured: true,
          },
        },
        embeddingStore: {
          type: fetchedEmbeddingStore?.type || "opensearch",
        },
      };

      setSettings({
        current: initialSettings,
        original: initialSettings,
        hasChanges: false,
      });
    }
  }, [providerData]);

  // Check if current settings differ from original
  useEffect(() => {
    const hasChanges =
      JSON.stringify(settings.current) !== JSON.stringify(settings.original);
    setSettings((prev) => ({
      ...prev,
      hasChanges,
    }));
  }, [settings.current, settings.original]);

  // Handle toggle change
  const handleToggleChange = (enabled: boolean) => {
    setSettings((prev) => ({
      ...prev,
      current: {
        ...prev.current,
        isEnabled: enabled,
      },
    }));
  };

  // Handle provider type change
  const handleProviderTypeChange = (
    providerType: "twelvelabs-api" | "twelvelabs-bedrock",
  ) => {
    if (providerType === "twelvelabs-api") {
      // Open API key dialog for Twelve Labs API
      setIsEditingApiKey(false);
      setApiKeyInput("");
      setIsApiKeyDialogOpen(true);
    } else {
      // No API key needed for Bedrock
      setSettings((prev) => ({
        ...prev,
        current: {
          ...prev.current,
          provider: {
            type: "twelvelabs-bedrock",
            config: {
              id: "",
              name: SYSTEM_SETTINGS_CONFIG.PROVIDERS.TWELVE_LABS_BEDROCK.name,
              type: "twelvelabs-bedrock",
              apiKey: "",
              isConfigured: true,
              isEnabled: true,
            },
          },
        },
      }));
    }
  };

  // Handle embedding store change
  const handleEmbeddingStoreChange = (
    storeType: "opensearch" | "s3-vector",
  ) => {
    setSettings((prev) => ({
      ...prev,
      current: {
        ...prev.current,
        embeddingStore: {
          type: storeType,
        },
      },
    }));
  };

  // Handle saving only embedding store changes
  const handleSaveEmbeddingStore = async () => {
    try {
      const { current } = settings;

      // Build embedding store payload
      const embeddingStorePayload = {
        type: current.embeddingStore.type,
        isEnabled: current.isEnabled,
      };

      // Always use updateProvider to save embedding store settings
      await updateProvider.mutateAsync({
        embeddingStore: embeddingStorePayload,
      });

      // Update original embedding store to match current (changes saved)
      setSettings((prev) => ({
        ...prev,
        original: {
          ...prev.original,
          embeddingStore: prev.current.embeddingStore,
        },
        hasChanges:
          JSON.stringify(prev.current) !==
          JSON.stringify({
            ...prev.original,
            embeddingStore: prev.current.embeddingStore,
          }),
      }));

      return true;
    } catch (error) {
      console.error("Error saving embedding store settings:", error);
      return false;
    }
  };

  // Handle API key dialog
  const handleOpenApiKeyDialog = (isEdit = false) => {
    setIsEditingApiKey(isEdit);
    setApiKeyInput(
      isEdit && settings.current.provider.config?.apiKey
        ? "••••••••••••••••"
        : "",
    );
    setIsApiKeyDialogOpen(true);
  };

  const handleCloseApiKeyDialog = () => {
    setIsApiKeyDialogOpen(false);
    setApiKeyInput("");
  };

  const handleSaveApiKey = async () => {
    if (apiKeyInput && apiKeyInput !== "••••••••••••••••") {
      const providerConfig: SearchProvider = {
        id: settings.current.provider.config?.id || "",
        name: SYSTEM_SETTINGS_CONFIG.PROVIDERS.TWELVE_LABS_API.name,
        type: "twelvelabs",
        apiKey: apiKeyInput,
        endpoint:
          SYSTEM_SETTINGS_CONFIG.PROVIDERS.TWELVE_LABS_API.defaultEndpoint,
        isConfigured: true,
        isEnabled: true,
      };

      // Update local state first
      setSettings((prev) => ({
        ...prev,
        current: {
          ...prev.current,
          provider: {
            type: "twelvelabs-api",
            config: providerConfig,
          },
        },
      }));

      // Build embedding store payload
      const embeddingStorePayload = {
        type: settings.current.embeddingStore.type,
        isEnabled: settings.current.isEnabled,
      };

      // Save to API immediately with the new API key
      if (isEditingApiKey && providerConfig.id) {
        // Update existing provider
        await updateProvider.mutateAsync({
          apiKey: providerConfig.apiKey,
          endpoint: providerConfig.endpoint,
          isEnabled: settings.current.isEnabled,
          embeddingStore: embeddingStorePayload,
        });
      } else {
        // Create new provider
        await createProvider.mutateAsync({
          name: providerConfig.name,
          type: providerConfig.type,
          apiKey: providerConfig.apiKey,
          endpoint: providerConfig.endpoint,
          isEnabled: settings.current.isEnabled,
          embeddingStore: embeddingStorePayload,
        });
      }

      // Update original to match current (changes saved)
      setSettings((prev) => ({
        ...prev,
        original: prev.current,
        hasChanges: false,
      }));

      return true;
    }
    return false;
  };

  // Handle save all changes
  const handleSave = async () => {
    try {
      const { current } = settings;

      // Build embedding store payload
      const embeddingStorePayload = {
        type: current.embeddingStore.type,
        isEnabled: current.isEnabled,
      };

      if (
        current.provider.config &&
        current.provider.type === "twelvelabs-api"
      ) {
        if (isEditingApiKey && current.provider.config.id) {
          // Update existing provider
          await updateProvider.mutateAsync({
            apiKey: current.provider.config.apiKey,
            endpoint: current.provider.config.endpoint,
            isEnabled: current.isEnabled,
            embeddingStore: embeddingStorePayload,
          });
        } else {
          // Create new provider
          await createProvider.mutateAsync({
            name: current.provider.config.name,
            type: current.provider.config.type,
            apiKey: current.provider.config.apiKey,
            endpoint: current.provider.config.endpoint,
            isEnabled: current.isEnabled,
            embeddingStore: embeddingStorePayload,
          });
        }
      } else if (current.provider.type === "twelvelabs-bedrock") {
        // For Bedrock, we still need to save embedding store settings
        await updateProvider.mutateAsync({
          isEnabled: current.isEnabled,
          embeddingStore: embeddingStorePayload,
        });
      }

      // Update original to match current (changes saved)
      setSettings((prev) => ({
        ...prev,
        original: prev.current,
        hasChanges: false,
      }));

      return true;
    } catch (error) {
      console.error("Error saving settings:", error);
      return false;
    }
  };

  // Handle cancel changes
  const handleCancel = () => {
    setSettings((prev) => ({
      ...prev,
      current: prev.original,
      hasChanges: false,
    }));
  };

  return {
    settings: settings.current,
    originalSettings: settings.original,
    hasChanges: settings.hasChanges,
    isLoading: isProviderLoading,
    error: providerError,

    // Dialog state
    isApiKeyDialogOpen,
    apiKeyInput,
    isEditingApiKey,

    // Handlers
    handleToggleChange,
    handleProviderTypeChange,
    handleEmbeddingStoreChange,
    handleSaveEmbeddingStore,
    handleOpenApiKeyDialog,
    handleCloseApiKeyDialog,
    handleSaveApiKey,
    handleSave,
    handleCancel,

    // Mutations
    isSaving: createProvider.isPending || updateProvider.isPending,

    // Dialog input handlers
    setApiKeyInput,
  };
};

export const useSystemSettingsManager = () => {
  const [provider, setProvider] = useState<SearchProvider>({
    id: "",
    name: SYSTEM_SETTINGS_CONFIG.PROVIDERS.TWELVE_LABS_API.name,
    type: SYSTEM_SETTINGS_CONFIG.PROVIDERS.TWELVE_LABS_API.type,
    apiKey: "",
    endpoint: SYSTEM_SETTINGS_CONFIG.PROVIDERS.TWELVE_LABS_API.defaultEndpoint,
    isConfigured: false,
    isEnabled: true,
  });

  const [isProviderDialogOpen, setIsProviderDialogOpen] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [newProviderDetails, setNewProviderDetails] = useState<
    Partial<SearchProvider>
  >({
    apiKey: "",
    endpoint: SYSTEM_SETTINGS_CONFIG.PROVIDERS.TWELVE_LABS_API.defaultEndpoint,
  });

  // Fetch the current search provider
  const {
    data: providerData,
    isLoading: isProviderLoading,
    error: providerError,
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
        isConfigured: true,
      });
    }
  }, [providerData]);

  // Handler for opening the add provider dialog
  const handleAddProviderClick = () => {
    setIsEditMode(false);
    setNewProviderDetails({
      apiKey: "",
      endpoint:
        SYSTEM_SETTINGS_CONFIG.PROVIDERS.TWELVE_LABS_API.defaultEndpoint,
    });
    setIsProviderDialogOpen(true);
  };

  // Handler for opening the edit provider dialog
  const handleEditProviderClick = () => {
    setIsEditMode(true);
    setNewProviderDetails({
      apiKey: provider.apiKey || "",
      endpoint:
        provider.endpoint ||
        SYSTEM_SETTINGS_CONFIG.PROVIDERS.TWELVE_LABS_API.defaultEndpoint,
    });
    setIsProviderDialogOpen(true);
  };

  // Handler for closing the dialog
  const handleCloseDialog = () => {
    setIsProviderDialogOpen(false);
  };

  // Handler for text field changes
  const handleTextFieldChange =
    (field: keyof SearchProvider) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
      setNewProviderDetails({
        ...newProviderDetails,
        [field]: event.target.value,
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
            isEnabled: true,
          });
        } else {
          // Create new provider
          await createProvider.mutateAsync({
            name: SYSTEM_SETTINGS_CONFIG.PROVIDERS.TWELVE_LABS_API.name,
            type: SYSTEM_SETTINGS_CONFIG.PROVIDERS.TWELVE_LABS_API.type,
            apiKey: newProviderDetails.apiKey || "",
            endpoint: newProviderDetails.endpoint,
            isEnabled: true,
          });
        }

        // Close the dialog after successful operation
        handleCloseDialog();
      } catch (error) {
        console.error("Error configuring provider:", error);
      }
    }
  };

  // Handler for resetting the provider
  const handleResetProvider = async () => {
    if (provider.id) {
      try {
        await updateProvider.mutateAsync({
          apiKey: "",
          isEnabled: false,
        });

        setProvider({
          ...provider,
          apiKey: "",
          isConfigured: false,
          isEnabled: false,
        });
      } catch (error) {
        console.error("Error resetting provider:", error);
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
    setProvider,
  };
};
