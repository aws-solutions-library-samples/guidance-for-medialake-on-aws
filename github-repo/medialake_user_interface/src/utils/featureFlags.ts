import React from "react";

/**
 * Utility functions for working with feature flags
 */

/**
 * Get the value of a feature flag
 * @param flagName The name of the feature flag to check
 * @param defaultValue The default value to return if the flag doesn't exist
 * @returns The value of the feature flag, or the default value if not found
 */
export const getFeatureFlag = async (
  flagName: string,
  defaultValue: boolean = false,
): Promise<boolean> => {
  try {
    const response = await fetch("/feature-flags.json");
    if (!response.ok) {
      console.warn(
        `Failed to fetch feature flags: ${response.status} ${response.statusText}`,
      );
      return defaultValue;
    }

    const flags = await response.json();
    if (flags[flagName] && typeof flags[flagName].value === "boolean") {
      return flags[flagName].value;
    }

    return defaultValue;
  } catch (error) {
    console.error("Error fetching feature flags:", error);
    return defaultValue;
  }
};

/**
 * React hook to use feature flags in components
 * @param flagName The name of the feature flag to check
 * @param defaultValue The default value to return if the flag doesn't exist
 * @returns An object containing the flag value and loading state
 */
export const useFeatureFlag = (
  flagName: string,
  defaultValue: boolean = false,
) => {
  const [flagValue, setFlagValue] = React.useState<boolean>(defaultValue);
  const [isLoading, setIsLoading] = React.useState<boolean>(true);

  React.useEffect(() => {
    const fetchFlag = async () => {
      setIsLoading(true);
      try {
        const value = await getFeatureFlag(flagName, defaultValue);
        setFlagValue(value);
      } catch (error) {
        console.error(`Error fetching feature flag ${flagName}:`, error);
        setFlagValue(defaultValue);
      } finally {
        setIsLoading(false);
      }
    };

    fetchFlag();
  }, [flagName, defaultValue]);

  return { value: flagValue, isLoading };
};
