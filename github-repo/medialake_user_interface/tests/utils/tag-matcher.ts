/**
 * Tag-based filtering utilities for AWS resource discovery
 * Provides flexible tag matching capabilities with support for multiple operators
 */

export interface TagFilter {
  key: string;
  values: string[];
  operator: "equals" | "contains" | "startsWith";
}

export interface AWSTag {
  Key: string;
  Value: string;
}

export interface StandardTagPatterns {
  APPLICATION_TAG: TagFilter;
  ENVIRONMENT_TAG: TagFilter;
  TESTING_TAG: TagFilter;
}

/**
 * Standard tag patterns for MediaLake resource discovery
 */
export const STANDARD_TAG_PATTERNS: StandardTagPatterns = {
  APPLICATION_TAG: {
    key: "Application",
    values: ["medialake"],
    operator: "equals",
  },
  ENVIRONMENT_TAG: {
    key: "Environment",
    values: ["dev", "staging", "prod"],
    operator: "equals",
  },
  TESTING_TAG: {
    key: "Testing",
    values: ["enabled"],
    operator: "equals",
  },
};

/**
 * Utility class for tag-based filtering and matching operations
 */
export class TagMatcher {
  /**
   * Check if a resource's tags match the provided filters
   * @param resourceTags - Array of AWS tags from the resource
   * @param filters - Array of tag filters to match against
   * @returns true if all filters match, false otherwise
   */
  static matchesTags(resourceTags: AWSTag[], filters: TagFilter[]): boolean {
    if (!resourceTags || resourceTags.length === 0) {
      return filters.length === 0;
    }

    // All filters must match for the resource to be considered a match
    return filters.every((filter) => this.matchesFilter(resourceTags, filter));
  }

  /**
   * Check if a single filter matches any of the resource tags
   * @param resourceTags - Array of AWS tags from the resource
   * @param filter - Single tag filter to match
   * @returns true if the filter matches, false otherwise
   */
  private static matchesFilter(
    resourceTags: AWSTag[],
    filter: TagFilter,
  ): boolean {
    const matchingTag = resourceTags.find((tag) => tag.Key === filter.key);

    if (!matchingTag) {
      return false;
    }

    return filter.values.some((filterValue) => {
      switch (filter.operator) {
        case "equals":
          return matchingTag.Value === filterValue;
        case "contains":
          return matchingTag.Value.toLowerCase().includes(
            filterValue.toLowerCase(),
          );
        case "startsWith":
          return matchingTag.Value.toLowerCase().startsWith(
            filterValue.toLowerCase(),
          );
        default:
          return false;
      }
    });
  }

  /**
   * Convert TagFilter array to AWS SDK TagFilter format
   * @param filters - Array of TagFilter objects
   * @returns Array in AWS SDK TagFilter format
   */
  static convertToAWSTagFilters(
    filters: TagFilter[],
  ): Array<{ Key: string; Values: string[] }> {
    return filters.map((filter) => ({
      Key: filter.key,
      Values: filter.values,
    }));
  }

  /**
   * Convert AWS tags array to a simple key-value record
   * @param awsTags - Array of AWS tags
   * @returns Record with tag keys as properties and values as strings
   */
  static convertToTagRecord(awsTags: AWSTag[]): Record<string, string> {
    return awsTags.reduce(
      (acc, tag) => {
        acc[tag.Key] = tag.Value;
        return acc;
      },
      {} as Record<string, string>,
    );
  }

  /**
   * Create a cache key from resource type and tag filters
   * @param resourceType - AWS resource type identifier
   * @param filters - Array of tag filters
   * @returns String cache key
   */
  static generateCacheKey(resourceType: string, filters: TagFilter[]): string {
    const filterKey = filters
      .map((f) => `${f.key}:${f.operator}:${f.values.join(",")}`)
      .sort()
      .join("|");

    return `${resourceType}:${filterKey}`;
  }

  /**
   * Get environment-specific tag filters
   * @param environment - Target environment (dev, staging, prod)
   * @returns Array of tag filters for the specified environment
   */
  static getEnvironmentFilters(environment: string = "dev"): TagFilter[] {
    return [
      STANDARD_TAG_PATTERNS.APPLICATION_TAG,
      {
        key: "Environment",
        values: [environment],
        operator: "equals",
      },
      STANDARD_TAG_PATTERNS.TESTING_TAG,
    ];
  }

  /**
   * Validate that required tags are present on a resource
   * @param resourceTags - Array of AWS tags from the resource
   * @param requiredTags - Array of required tag keys
   * @returns Object with validation result and missing tags
   */
  static validateRequiredTags(
    resourceTags: AWSTag[],
    requiredTags: string[],
  ): { isValid: boolean; missingTags: string[] } {
    const presentTagKeys = resourceTags.map((tag) => tag.Key);
    const missingTags = requiredTags.filter(
      (required) => !presentTagKeys.includes(required),
    );

    return {
      isValid: missingTags.length === 0,
      missingTags,
    };
  }
}
