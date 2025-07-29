// src/permissions/utils/global-permission-cache.ts

import { User } from "../types/permission.types";
import { AppAbility, createAppAbility } from "../types/ability.types";

interface SerializedAbility {
  rules: any[];
}

interface GlobalCacheData {
  user: User;
  customPermissions: string[];
  ability: SerializedAbility;
  permissionSets: any[];
  token: string;
  expiresAt: number;
  lastUpdated: number;
}

interface PermissionCheckCache {
  [key: string]: {
    result: boolean;
    timestamp: number;
  };
}

/**
 * Global permission cache that stores all authentication and permission data
 * This cache is only updated when tokens are refreshed, not on every component mount
 */
class GlobalPermissionCache {
  private static CACHE_KEY = "medialake_global_permission_cache";
  private static CHECK_CACHE_KEY = "medialake_permission_checks";
  private static instance: GlobalPermissionCache;

  private memoryCache: GlobalCacheData | null = null;
  private checkCache: PermissionCheckCache = {};
  private readonly TTL = 5 * 60 * 1000; // 5 minutes for permission checks

  constructor() {
    // Load existing cache from localStorage on initialization
    this.loadFromStorage();
  }

  static getInstance(): GlobalPermissionCache {
    if (!GlobalPermissionCache.instance) {
      GlobalPermissionCache.instance = new GlobalPermissionCache();
    }
    return GlobalPermissionCache.instance;
  }

  /**
   * Set the global cache with all permission data
   */
  setGlobalCache(
    user: User,
    customPermissions: string[],
    ability: AppAbility,
    permissionSets: any[],
    token: string,
    expiresIn: number,
  ): void {
    const serializedAbility = this.serializeAbility(ability);
    const cacheData: GlobalCacheData = {
      user,
      customPermissions,
      ability: serializedAbility,
      permissionSets,
      token,
      expiresAt: Date.now() + expiresIn * 1000,
      lastUpdated: Date.now(),
    };

    this.memoryCache = cacheData;

    try {
      // Store in localStorage for persistence across page reloads
      localStorage.setItem(
        GlobalPermissionCache.CACHE_KEY,
        JSON.stringify(cacheData),
      );
      console.log(
        "Global permission cache updated, expires at:",
        new Date(cacheData.expiresAt).toISOString(),
      );
    } catch (error) {
      console.error("Failed to store global permission cache:", error);
    }
  }

  /**
   * Get the global cache if valid, with ability deserialization
   */
  getGlobalCache(currentToken: string): {
    user: User;
    customPermissions: string[];
    ability: AppAbility;
    permissionSets: any[];
    token: string;
    expiresAt: number;
    lastUpdated: number;
  } | null {
    // Check memory cache first
    if (this.memoryCache && this.isValidCache(this.memoryCache, currentToken)) {
      return {
        ...this.memoryCache,
        ability: this.deserializeAbility(this.memoryCache.ability),
      };
    }

    // Check localStorage
    try {
      const stored = localStorage.getItem(GlobalPermissionCache.CACHE_KEY);
      if (!stored) return null;

      const cacheData: GlobalCacheData = JSON.parse(stored);

      if (this.isValidCache(cacheData, currentToken)) {
        // Restore to memory cache
        this.memoryCache = cacheData;
        return {
          ...cacheData,
          ability: this.deserializeAbility(cacheData.ability),
        };
      }
    } catch (error) {
      console.error("Failed to read global permission cache:", error);
    }

    return null;
  }

  /**
   * Check if a permission is cached
   */
  getPermissionCheck(cacheKey: string): boolean | null {
    const cached = this.checkCache[cacheKey];
    if (!cached) return null;

    // Check if expired
    if (Date.now() - cached.timestamp > this.TTL) {
      delete this.checkCache[cacheKey];
      return null;
    }

    return cached.result;
  }

  /**
   * Cache a permission check result
   */
  setPermissionCheck(cacheKey: string, result: boolean): void {
    this.checkCache[cacheKey] = {
      result,
      timestamp: Date.now(),
    };

    // Clean up old entries periodically
    this.cleanupPermissionChecks();
  }

  /**
   * Check if the global cache is valid
   */
  isValid(currentToken: string): boolean {
    const cache = this.getGlobalCache(currentToken);
    return cache !== null;
  }

  /**
   * Clear all caches
   */
  clear(): void {
    this.memoryCache = null;
    this.checkCache = {};

    try {
      localStorage.removeItem(GlobalPermissionCache.CACHE_KEY);
      localStorage.removeItem(GlobalPermissionCache.CHECK_CACHE_KEY);
      console.log("Global permission cache cleared");
    } catch (error) {
      console.error("Failed to clear global permission cache:", error);
    }
  }

  /**
   * Update only the token in the cache (for token refresh scenarios)
   */
  updateToken(newToken: string, expiresIn: number): void {
    if (this.memoryCache) {
      this.memoryCache.token = newToken;
      this.memoryCache.expiresAt = Date.now() + expiresIn * 1000;
      this.memoryCache.lastUpdated = Date.now();

      try {
        localStorage.setItem(
          GlobalPermissionCache.CACHE_KEY,
          JSON.stringify(this.memoryCache),
        );
        console.log("Token updated in global cache");
      } catch (error) {
        console.error("Failed to update token in cache:", error);
      }
    }
  }

  /**
   * Get cache statistics for debugging
   */
  getCacheStats(): {
    hasGlobalCache: boolean;
    cacheAge: number | null;
    expiresIn: number | null;
    permissionChecksCount: number;
  } {
    const cache = this.memoryCache;
    return {
      hasGlobalCache: cache !== null,
      cacheAge: cache ? Date.now() - cache.lastUpdated : null,
      expiresIn: cache ? cache.expiresAt - Date.now() : null,
      permissionChecksCount: Object.keys(this.checkCache).length,
    };
  }

  private isValidCache(cache: GlobalCacheData, currentToken: string): boolean {
    // Check if cache is expired
    if (Date.now() >= cache.expiresAt) {
      console.log("Global permission cache expired");
      return false;
    }

    // Check if token matches
    if (cache.token !== currentToken) {
      console.log("Token mismatch in global cache");
      return false;
    }

    return true;
  }

  private loadFromStorage(): void {
    try {
      const stored = localStorage.getItem(GlobalPermissionCache.CACHE_KEY);
      if (stored) {
        const cacheData: GlobalCacheData = JSON.parse(stored);
        // Don't load expired cache
        if (Date.now() < cacheData.expiresAt) {
          this.memoryCache = cacheData;
        }
      }

      const checkCache = localStorage.getItem(
        GlobalPermissionCache.CHECK_CACHE_KEY,
      );
      if (checkCache) {
        this.checkCache = JSON.parse(checkCache);
      }
    } catch (error) {
      console.error("Failed to load cache from storage:", error);
    }
  }

  private cleanupPermissionChecks(): void {
    const now = Date.now();
    const keysToDelete: string[] = [];

    for (const [key, cached] of Object.entries(this.checkCache)) {
      if (now - cached.timestamp > this.TTL) {
        keysToDelete.push(key);
      }
    }

    keysToDelete.forEach((key) => delete this.checkCache[key]);

    // Persist cleaned cache
    try {
      localStorage.setItem(
        GlobalPermissionCache.CHECK_CACHE_KEY,
        JSON.stringify(this.checkCache),
      );
    } catch (error) {
      console.error("Failed to persist permission check cache:", error);
    }
  }

  private serializeAbility(ability: AppAbility): any {
    // Convert ability to a serializable format
    return {
      rules: ability.rules,
      // Store other necessary ability properties
    };
  }

  private deserializeAbility(serializedAbility: SerializedAbility): AppAbility {
    // Recreate ability from serialized format
    const ability = createAppAbility();

    // Restore the rules
    if (serializedAbility && serializedAbility.rules) {
      ability.update(serializedAbility.rules);
    }

    return ability;
  }
}

// Export singleton instance
export const globalPermissionCache = GlobalPermissionCache.getInstance();
