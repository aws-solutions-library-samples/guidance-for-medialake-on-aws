import React, { useState, useEffect } from "react";
import {
  useSearchProvider,
  useCreateSearchProvider,
  useUpdateSearchProvider,
  useDeleteSearchProvider,
} from "../api/systemHooks";
import {
  SearchProvider,
  SemanticSearchSettings,
  SystemSettingsState,
  ProviderMetadata,
} from "../types/system.types";

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
        type: "none",
        config: null,
      },
      embeddingStore: {
        type: "opensearch",
      },
    },
    original: {
      isEnabled: false,
      provider: {
        type: "none",
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

  // Fetch the current search provider and available providers
  const {
    data: providerData,
    isLoading: isProviderLoading,
    error: providerError,
  } = useSearchProvider();

  // Mutations for creating, updating, and deleting the provider
  const createProvider = useCreateSearchProvider();
  const updateProvider = useUpdateSearchProvider();
  const deleteProvider = useDeleteSearchProvider();

  // Helper function to get provider config by type from API data
  const getProviderConfig = (providerType: string): ProviderMetadata | undefined => {
    const availableProviders = providerData?.data?.availableProviders;
    if (!availableProviders) return undefined;
    return availableProviders[providerType];
  };

  // Initialize settings from fetched data
  useEffect(() => {
    if (providerData?.data?.searchProvider) {
      const fetchedProvider = providerData.data.searchProvider;
      const fetchedEmbeddingStore = providerData.data.embeddingStore;

      // Preserve provider information to track existence, even if not fully configured
      const isConfigured = fetchedProvider.isConfigured || false;
      const hasId = !!fetchedProvider.id; // Provider exists in database if it has an ID

      // Show "none" in UI if not configured, but preserve actual type for backend operations
      const displayType = isConfigured
        ? fetchedProvider.type === "twelvelabs-bedrock"
          ? "twelvelabs-bedrock"
          : fetchedProvider.type === "twelvelabs-bedrock-3-0"
            ? "twelvelabs-bedrock-3-0"
            : fetchedProvider.type === "coactive"
              ? "coactive"
              : fetchedProvider.type === "twelvelabs-api"
                ? "twelvelabs-api"
                : "none"
        : "none";

      const initialSettings: SemanticSearchSettings = {
        isEnabled: fetchedProvider.isEnabled || false,
        provider: {
          type: displayType,
          config: hasId
            ? {
                ...fetchedProvider,
                isConfigured,
              }
            : null,
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
    const hasChanges = JSON.stringify(settings.current) !== JSON.stringify(settings.original);
    setSettings((prev) => ({
      ...prev,
      hasChanges,
    }));
  }, [settings.current, settings.original]);

  // Handle toggle change with immediate save
  const handleToggleChange = async (enabled: boolean) => {
    // Update local state immediately for responsive UI
    setSettings((prev) => ({
      ...prev,
      current: {
        ...prev.current,
        isEnabled: enabled,
      },
    }));

    if (enabled) {
      // Handle enabling: only save if provider is configured
      if (settings.current.provider.config?.isConfigured) {
        try {
          const embeddingStorePayload = {
            type: settings.current.embeddingStore.type,
            isEnabled: enabled,
          };

          await updateProvider.mutateAsync({
            isEnabled: enabled,
            embeddingStore: embeddingStorePayload,
          });

          // Update original state to reflect saved changes
          setSettings((prev) => ({
            ...prev,
            original: {
              ...prev.original,
              isEnabled: enabled,
            },
          }));
        } catch (error) {
          console.error("Failed to save toggle state:", error);
          // Revert local state on error
          setSettings((prev) => ({
            ...prev,
            current: {
              ...prev.current,
              isEnabled: !enabled,
            },
          }));
          throw error;
        }
      }
      // If no provider configured, just keep local state - user needs to select provider first
    } else {
      // Handle disabling: delete the provider configuration and reset to default state
      if (settings.original.provider.config?.id) {
        try {
          await deleteProvider.mutateAsync();

          // Reset to default state (no provider selected)
          const defaultSettings = {
            isEnabled: false,
            provider: {
              type: "none" as const,
              config: null,
            },
            embeddingStore: {
              type: "opensearch" as const,
            },
          };

          setSettings((prev) => ({
            ...prev,
            current: defaultSettings,
            original: defaultSettings,
          }));
        } catch (error) {
          console.error("Failed to delete provider:", error);
          // Revert local state on error
          setSettings((prev) => ({
            ...prev,
            current: {
              ...prev.current,
              isEnabled: !enabled,
            },
          }));
          throw error;
        }
      } else {
        // No provider to delete, just update local state
        setSettings((prev) => ({
          ...prev,
          original: {
            ...prev.original,
            isEnabled: enabled,
          },
        }));
      }
    }
  };

  // Handle provider type change
  const handleProviderTypeChange = async (
    providerType:
      | "none"
      | "twelvelabs-api"
      | "twelvelabs-bedrock"
      | "twelvelabs-bedrock-3-0"
      | "coactive"
  ) => {
    if (providerType === "none") {
      // Reset to no provider
      setSettings((prev) => ({
        ...prev,
        current: {
          ...prev.current,
          isEnabled: false,
          provider: {
            type: "none",
            config: null,
          },
        },
      }));
    } else if (providerType === "twelvelabs-api") {
      // Update provider type first, then open API key dialog
      setSettings((prev) => ({
        ...prev,
        current: {
          ...prev.current,
          provider: {
            type: "twelvelabs-api",
            config: null,
          },
        },
      }));
      setIsEditingApiKey(false);
      setApiKeyInput("");
      setIsApiKeyDialogOpen(true);
    } else if (providerType === "coactive") {
      // Update provider type first, then open API key dialog
      setSettings((prev) => ({
        ...prev,
        current: {
          ...prev.current,
          provider: {
            type: "coactive",
            config: null,
          },
          // For Coactive, we don't use embedding stores, so set to a default
          embeddingStore: {
            type: "opensearch", // This won't be used but needed for type consistency
          },
        },
      }));
      setIsEditingApiKey(false);
      setApiKeyInput("");
      setIsApiKeyDialogOpen(true);
    } else {
      // For Bedrock variants, save immediately since no API key is needed
      try {
        const embeddingStorePayload = {
          type: settings.current.embeddingStore.type,
          isEnabled: settings.current.isEnabled,
        };

        const providerExists = settings.original.provider.config?.id;

        // Get provider config dynamically
        const providerConfig = getProviderConfig(providerType);
        if (!providerConfig) {
          console.error(`Unknown provider type: ${providerType}`);
          return;
        }

        if (providerExists) {
          // Update existing provider to selected type
          const updatePayload: any = {
            type: providerType,
            isEnabled: settings.current.isEnabled,
            embeddingStore: embeddingStorePayload,
          };

          // Only include dimensions if the provider config has them
          if ("dimensions" in providerConfig && providerConfig.dimensions) {
            updatePayload.dimensions = providerConfig.dimensions[0];
          }

          // Include inference_provider if available
          if ("inference_provider" in providerConfig) {
            updatePayload.inference_provider = providerConfig.inference_provider;
          }

          await updateProvider.mutateAsync(updatePayload);
        } else {
          // Create new provider with selected type
          const createPayload: any = {
            name: providerConfig.name,
            type: providerType,
            apiKey: "", // Not needed for Bedrock
            isEnabled: settings.current.isEnabled,
            embeddingStore: embeddingStorePayload,
          };

          // Only include dimensions if the provider config has them
          if ("dimensions" in providerConfig && providerConfig.dimensions) {
            createPayload.dimensions = providerConfig.dimensions[0];
          }

          // Include inference_provider if available
          if ("inference_provider" in providerConfig) {
            createPayload.inference_provider = providerConfig.inference_provider;
          }

          await createProvider.mutateAsync(createPayload);
        }

        // Use same config for state update
        const selectedProviderConfig = providerConfig;

        // Update local state after successful save
        setSettings((prev) => ({
          ...prev,
          current: {
            ...prev.current,
            isEnabled: true, // Enable search when Bedrock provider is configured
            provider: {
              type: providerType as "twelvelabs-bedrock" | "twelvelabs-bedrock-3-0",
              config: {
                id: providerExists ? prev.original.provider.config?.id || "" : "",
                name: selectedProviderConfig.name,
                type: providerType,
                apiKey: "",
                isConfigured: true,
                isEnabled: true,
              },
            },
          },
          original: {
            ...prev.current,
            isEnabled: true, // Update original state too
            provider: {
              type: providerType as "twelvelabs-bedrock" | "twelvelabs-bedrock-3-0",
              config: {
                id: providerExists ? prev.original.provider.config?.id || "" : "",
                name: selectedProviderConfig.name,
                type: providerType,
                apiKey: "",
                isConfigured: true,
                isEnabled: true,
              },
            },
          },
          hasChanges: false,
        }));
      } catch (error) {
        console.error("Failed to save Bedrock provider:", error);
        // Could add error notification here
      }
    }
  };

  // Handle embedding store change
  const handleEmbeddingStoreChange = (storeType: "opensearch" | "s3-vector") => {
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
    setApiKeyInput(isEdit && settings.current.provider.config?.apiKey ? "••••••••••••••••" : "");
    setIsApiKeyDialogOpen(true);
  };

  const handleCloseApiKeyDialog = () => {
    setIsApiKeyDialogOpen(false);
    setApiKeyInput("");
  };

  const handleSaveApiKey = async () => {
    if (apiKeyInput && apiKeyInput !== "••••••••••••••••") {
      // Determine which provider we're configuring based on current selection
      const currentProviderType = settings.current.provider.type;

      let providerConfig: SearchProvider;
      let providerTypeForState: "twelvelabs-api" | "twelvelabs-bedrock" | "coactive";

      // Get provider metadata from API
      const availableProviders = providerData?.data?.availableProviders;

      if (currentProviderType === "coactive" && availableProviders?.coactive) {
        const metadata = availableProviders.coactive;
        providerConfig = {
          id: settings.current.provider.config?.id || "",
          name: metadata.name,
          type: "coactive",
          apiKey: apiKeyInput,
          endpoint: metadata.defaultEndpoint,
          isConfigured: true,
          isEnabled: true,
        };
        providerTypeForState = "coactive";
      } else if (availableProviders?.["twelvelabs-api"]) {
        // Default to TwelveLabs API
        const metadata = availableProviders["twelvelabs-api"];
        providerConfig = {
          id: settings.current.provider.config?.id || "",
          name: metadata.name,
          type: "twelvelabs-api",
          apiKey: apiKeyInput,
          endpoint: metadata.defaultEndpoint,
          isConfigured: true,
          isEnabled: true,
        };
        providerTypeForState = "twelvelabs-api";
      } else {
        console.error("Provider metadata not available from API");
        return false;
      }

      // Update local state first
      setSettings((prev) => ({
        ...prev,
        current: {
          ...prev.current,
          provider: {
            type: providerTypeForState,
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
      // Check if there's already a provider configured (any provider)
      const hasExistingProvider =
        settings.original.provider.config?.isConfigured || settings.original.provider.config?.id;

      if (hasExistingProvider) {
        // Update existing provider (supports type switching now)
        const updatePayload: any = {
          name: providerConfig.name,
          type: providerConfig.type,
          apiKey: providerConfig.apiKey,
          endpoint: providerConfig.endpoint,
          isEnabled: settings.current.isEnabled,
          embeddingStore: embeddingStorePayload,
        };

        // Include inference_provider if available from metadata
        const metadata = availableProviders?.[providerConfig.type];
        if (metadata && "inference_provider" in metadata) {
          updatePayload.inference_provider = metadata.inference_provider;
        }

        await updateProvider.mutateAsync(updatePayload);
      } else {
        // Create new provider (first time setup)
        const createPayload: any = {
          name: providerConfig.name,
          type: providerConfig.type,
          apiKey: providerConfig.apiKey,
          endpoint: providerConfig.endpoint,
          isEnabled: settings.current.isEnabled,
          embeddingStore: embeddingStorePayload,
        };

        // Include inference_provider if available from metadata
        const metadata = availableProviders?.[providerConfig.type];
        if (metadata && "inference_provider" in metadata) {
          createPayload.inference_provider = metadata.inference_provider;
        }

        await createProvider.mutateAsync(createPayload);
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

      // Use provider existence from original settings to determine POST vs PUT
      const providerExists = settings.original.provider.config?.id;

      if (
        current.provider.config &&
        (current.provider.type === "twelvelabs-api" || current.provider.type === "coactive")
      ) {
        if (providerExists) {
          // Update existing provider
          const updatePayload: any = {
            type: current.provider.config.type,
            apiKey: current.provider.config.apiKey,
            endpoint: current.provider.config.endpoint,
            isEnabled: current.isEnabled,
            embeddingStore: embeddingStorePayload,
          };

          // Include inference_provider if available from metadata
          const metadata = providerData?.data?.availableProviders?.[current.provider.config.type];
          if (metadata && "inference_provider" in metadata) {
            updatePayload.inference_provider = metadata.inference_provider;
          }

          await updateProvider.mutateAsync(updatePayload);
        } else {
          // Create new provider
          const createPayload: any = {
            name: current.provider.config.name,
            type: current.provider.config.type,
            apiKey: current.provider.config.apiKey,
            endpoint: current.provider.config.endpoint,
            isEnabled: current.isEnabled,
            embeddingStore: embeddingStorePayload,
          };

          // Include inference_provider if available from metadata
          const metadata = providerData?.data?.availableProviders?.[current.provider.config.type];
          if (metadata && "inference_provider" in metadata) {
            createPayload.inference_provider = metadata.inference_provider;
          }

          await createProvider.mutateAsync(createPayload);
        }
      } else if (
        current.provider.type === "twelvelabs-bedrock" ||
        current.provider.type === "twelvelabs-bedrock-3-0"
      ) {
        // For Bedrock variants, determine if we need to create or update
        const providerConfig = getProviderConfig(current.provider.type);
        if (!providerConfig) {
          console.error(`Unknown provider type: ${current.provider.type}`);
          return false;
        }

        if (providerExists) {
          // Update existing provider to Bedrock type
          const updatePayload: any = {
            isEnabled: current.isEnabled,
            embeddingStore: embeddingStorePayload,
          };

          // Only include dimensions if the provider config has them
          if ("dimensions" in providerConfig && providerConfig.dimensions) {
            updatePayload.dimensions = providerConfig.dimensions[0];
          }

          // Include inference_provider if available
          if ("inference_provider" in providerConfig) {
            updatePayload.inference_provider = providerConfig.inference_provider;
          }

          await updateProvider.mutateAsync(updatePayload);
        } else {
          // Create new Bedrock provider
          const createPayload: any = {
            name: providerConfig.name,
            type: current.provider.type,
            apiKey: "", // Not needed for Bedrock
            isEnabled: current.isEnabled,
            embeddingStore: embeddingStorePayload,
          };

          // Only include dimensions if the provider config has them
          if ("dimensions" in providerConfig && providerConfig.dimensions) {
            createPayload.dimensions = providerConfig.dimensions[0];
          }

          // Include inference_provider if available
          if ("inference_provider" in providerConfig) {
            createPayload.inference_provider = providerConfig.inference_provider;
          }

          await createProvider.mutateAsync(createPayload);
        }
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

    // Provider metadata from API
    availableProviders: providerData?.data?.availableProviders,
    availableEmbeddingStores: providerData?.data?.availableEmbeddingStores,

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
    isSaving: createProvider.isPending || updateProvider.isPending || deleteProvider.isPending,

    // Dialog input handlers
    setApiKeyInput,
  };
};

export const useSystemSettingsManager = () => {
  // Fetch the current search provider first
  const {
    data: providerData,
    isLoading: isProviderLoading,
    error: providerError,
  } = useSearchProvider();

  // Get default values from API
  const defaultProvider = providerData?.data?.availableProviders?.["twelvelabs-api"];

  const [provider, setProvider] = useState<SearchProvider>({
    id: "",
    name: defaultProvider?.name || "TwelveLabs Marengo Embed 2.7 API",
    type: defaultProvider?.type || "twelvelabs",
    apiKey: "",
    endpoint: defaultProvider?.defaultEndpoint || "https://api.twelvelabs.io/v1",
    isConfigured: false,
    isEnabled: true,
  });

  const [isProviderDialogOpen, setIsProviderDialogOpen] = useState(false);
  const [isEditMode, setIsEditMode] = useState(false);
  const [newProviderDetails, setNewProviderDetails] = useState<Partial<SearchProvider>>({
    apiKey: "",
    endpoint: defaultProvider?.defaultEndpoint || "https://api.twelvelabs.io/v1",
  });

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
    const defaultEndpoint = defaultProvider?.defaultEndpoint || "https://api.twelvelabs.io/v1";
    setIsEditMode(false);
    setNewProviderDetails({
      apiKey: "",
      endpoint: defaultEndpoint,
    });
    setIsProviderDialogOpen(true);
  };

  // Handler for opening the edit provider dialog
  const handleEditProviderClick = () => {
    const defaultEndpoint = defaultProvider?.defaultEndpoint || "https://api.twelvelabs.io/v1";
    setIsEditMode(true);
    setNewProviderDetails({
      apiKey: provider.apiKey || "",
      endpoint: provider.endpoint || defaultEndpoint,
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
            name: defaultProvider?.name || "TwelveLabs Marengo Embed 2.7 API",
            type: defaultProvider?.type || "twelvelabs",
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
