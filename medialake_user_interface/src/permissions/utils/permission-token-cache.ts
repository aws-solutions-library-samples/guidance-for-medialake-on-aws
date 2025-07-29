// src/permissions/utils/permission-token-cache.ts
import { User } from "../types/permission.types";

interface CachedPermissions {
  user: User;
  customPermissions: string[];
  token: string;
  expiresAt: number;
}

class PermissionTokenCache {
  private static CACHE_KEY = "medialake_permission_cache";

  /**
   * Store permissions with token information
   */
  static set(
    user: User,
    customPermissions: string[],
    token: string,
    expiresIn: number,
  ): void {
    const cacheData: CachedPermissions = {
      user,
      customPermissions,
      token,
      expiresAt: Date.now() + expiresIn * 1000, // Convert to milliseconds
    };

    try {
      localStorage.setItem(this.CACHE_KEY, JSON.stringify(cacheData));
      console.log(
        "Cached permissions until:",
        new Date(cacheData.expiresAt).toISOString(),
      );
    } catch (error) {
      console.error("Failed to cache permissions:", error);
    }
  }

  /**
   * Get cached permissions if valid
   */
  static get(
    currentToken: string,
  ): { user: User; customPermissions: string[] } | null {
    try {
      const cached = localStorage.getItem(this.CACHE_KEY);
      if (!cached) return null;

      const cacheData: CachedPermissions = JSON.parse(cached);

      // Check if cache is expired
      if (Date.now() >= cacheData.expiresAt) {
        console.log("Permission cache expired");
        this.clear();
        return null;
      }

      // Check if token matches
      if (cacheData.token !== currentToken) {
        console.log("Token mismatch, clearing permission cache");
        this.clear();
        return null;
      }

      console.log(
        "Using cached permissions, expires at:",
        new Date(cacheData.expiresAt).toISOString(),
      );
      return {
        user: cacheData.user,
        customPermissions: cacheData.customPermissions,
      };
    } catch (error) {
      console.error("Failed to read permission cache:", error);
      this.clear();
      return null;
    }
  }

  /**
   * Clear the cache
   */
  static clear(): void {
    try {
      localStorage.removeItem(this.CACHE_KEY);
      console.log("Permission cache cleared");
    } catch (error) {
      console.error("Failed to clear permission cache:", error);
    }
  }

  /**
   * Check if cache exists and is valid
   */
  static isValid(currentToken: string): boolean {
    const cached = this.get(currentToken);
    return cached !== null;
  }
}

export default PermissionTokenCache;
