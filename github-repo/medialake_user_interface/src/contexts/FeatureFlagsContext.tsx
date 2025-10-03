import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";

// Define the shape of the feature flags in the JSON file
interface FeatureFlagData {
  value: boolean;
  variant: string;
}

interface FeatureFlagsJson {
  [key: string]: FeatureFlagData;
}

// Define the shape of our transformed feature flags
interface FeatureFlags {
  [key: string]: boolean;
}

// Create the context
interface FeatureFlagsContextType {
  flags: FeatureFlags;
  isLoading: boolean;
  error: Error | null;
  refreshFlags: () => Promise<void>;
}

const defaultContext: FeatureFlagsContextType = {
  flags: {},
  isLoading: true,
  error: null,
  refreshFlags: async () => {},
};

const FeatureFlagsContext =
  createContext<FeatureFlagsContextType>(defaultContext);

// Configuration
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000; // ms
const FETCH_TIMEOUT = 5000; // ms

// Provider component
export const FeatureFlagsProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [flags, setFlags] = useState<FeatureFlags>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  // Function to fetch flags with retry logic
  const fetchFlags = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    let retries = 0;

    while (retries < MAX_RETRIES) {
      try {
        // Create an AbortController for timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT);

        const response = await fetch("/feature-flags.json", {
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
          throw new Error(`HTTP error! Status: ${response.status}`);
        }

        const data = (await response.json()) as FeatureFlagsJson;

        // Transform the data to a simple boolean map
        const transformedFlags: FeatureFlags = {};
        for (const [key, value] of Object.entries(data)) {
          transformedFlags[key] = value.value === true;
        }

        setFlags(transformedFlags);
        setIsLoading(false);
        console.log("FeatureFlagsContext: Successfully loaded feature flags");
        return; // Success, exit the retry loop
      } catch (err) {
        retries++;

        // Format the error message
        const errorMessage = err instanceof Error ? err.message : String(err);
        console.error(
          `FeatureFlagsContext: Error fetching feature flags (attempt ${retries}/${MAX_RETRIES}):`,
          errorMessage,
        );

        // If we've reached max retries, set the error state
        if (retries >= MAX_RETRIES) {
          setError(err instanceof Error ? err : new Error(String(err)));
          setIsLoading(false);
          return;
        }

        // Wait before retrying
        await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY));
      }
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchFlags();
  }, [fetchFlags]);

  // Provide a way to refresh flags
  const refreshFlags = useCallback(async () => {
    await fetchFlags();
  }, [fetchFlags]);

  return (
    <FeatureFlagsContext.Provider
      value={{ flags, isLoading, error, refreshFlags }}
    >
      {children}
    </FeatureFlagsContext.Provider>
  );
};

// Hook for using the feature flags
export const useFeatureFlag = (
  flagName: string,
  defaultValue: boolean = false,
): boolean => {
  const { flags, isLoading } = useContext(FeatureFlagsContext);

  // If still loading or flag doesn't exist, return the default value
  if (isLoading || !(flagName in flags)) {
    return defaultValue;
  }

  return flags[flagName];
};

// Hook for accessing the refresh function
export const useRefreshFeatureFlags = (): (() => Promise<void>) => {
  const { refreshFlags } = useContext(FeatureFlagsContext);
  return refreshFlags;
};
