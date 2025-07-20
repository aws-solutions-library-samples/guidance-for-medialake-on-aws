// src/permissions/utils/permission-cache.ts

/**
 * Simple in-memory cache for permission checks to improve performance
 * by avoiding redundant permission checks.
 */
class PermissionCache {
  private cache: Map<string, boolean>;
  private maxSize: number;
  private ttl: number; // Time to live in milliseconds
  private timestamps: Map<string, number>;

  constructor(maxSize = 1000, ttlInSeconds = 300) {
    this.cache = new Map<string, boolean>();
    this.timestamps = new Map<string, number>();
    this.maxSize = maxSize;
    this.ttl = ttlInSeconds * 1000;
  }

  /**
   * Get a cached permission check result
   * @param key The cache key
   * @returns The cached result or undefined if not found
   */
  get(key: string): boolean | undefined {
    console.log("Permission cache get:", key);
    this.cleanExpired();

    const timestamp = this.timestamps.get(key);
    if (timestamp === undefined) {
      console.log("Permission cache miss:", key);
      return undefined;
    }

    // Check if the entry has expired
    if (Date.now() - timestamp > this.ttl) {
      console.log("Permission cache expired:", key);
      this.delete(key);
      return undefined;
    }

    const value = this.cache.get(key);
    console.log("Permission cache hit:", key, value);
    return value;
  }

  /**
   * Set a permission check result in the cache
   * @param key The cache key
   * @param value The permission check result
   */
  set(key: string, value: boolean): void {
    console.log("Permission cache set:", key, value);

    // If the cache is full, remove the oldest entry
    if (this.cache.size >= this.maxSize) {
      this.removeOldest();
    }

    this.cache.set(key, value);
    this.timestamps.set(key, Date.now());
  }

  /**
   * Check if a key exists in the cache
   * @param key The cache key
   * @returns True if the key exists, false otherwise
   */
  has(key: string): boolean {
    return this.cache.has(key);
  }

  /**
   * Delete a key from the cache
   * @param key The cache key
   */
  delete(key: string): void {
    this.cache.delete(key);
    this.timestamps.delete(key);
  }

  /**
   * Clear the entire cache
   */
  clear(): void {
    console.log("Permission cache cleared");
    this.cache.clear();
    this.timestamps.clear();
  }

  /**
   * Remove expired entries from the cache
   */
  private cleanExpired(): void {
    const now = Date.now();
    for (const [key, timestamp] of this.timestamps.entries()) {
      if (now - timestamp > this.ttl) {
        this.delete(key);
      }
    }
  }

  /**
   * Remove the oldest entry from the cache
   */
  private removeOldest(): void {
    let oldestKey: string | null = null;
    let oldestTimestamp = Infinity;

    for (const [key, timestamp] of this.timestamps.entries()) {
      if (timestamp < oldestTimestamp) {
        oldestTimestamp = timestamp;
        oldestKey = key;
      }
    }

    if (oldestKey) {
      this.delete(oldestKey);
    }
  }
}

// Export a singleton instance of the cache
export const permissionCache = new PermissionCache();
