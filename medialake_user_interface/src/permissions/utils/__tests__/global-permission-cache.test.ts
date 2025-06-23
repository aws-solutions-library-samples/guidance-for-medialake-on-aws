// src/permissions/utils/__tests__/global-permission-cache.test.ts

import { globalPermissionCache } from '../global-permission-cache';
import { createAppAbility } from '../../types/ability.types';
import { User } from '../../types/permission.types';

// Mock localStorage
const localStorageMock = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
  clear: jest.fn(),
};
global.localStorage = localStorageMock as any;

describe('GlobalPermissionCache', () => {
  const mockUser: User = {
    id: 'test-user-id',
    username: 'testuser',
    email: 'test@example.com',
    groups: ['admin'],
  };

  const mockToken = 'mock.jwt.token';
  const mockCustomPermissions = ['read:assets', 'write:assets'];
  const mockAbility = createAppAbility();
  const mockPermissionSets = [{ id: 1, name: 'admin', permissions: [] }];

  beforeEach(() => {
    jest.clearAllMocks();
    globalPermissionCache.clear();
  });

  describe('setGlobalCache and getGlobalCache', () => {
    it('should store and retrieve global cache data', () => {
      const expiresIn = 3600; // 1 hour

      // Set cache
      globalPermissionCache.setGlobalCache(
        mockUser,
        mockCustomPermissions,
        mockAbility,
        mockPermissionSets,
        mockToken,
        expiresIn
      );

      // Get cache
      const cached = globalPermissionCache.getGlobalCache(mockToken);

      expect(cached).toBeTruthy();
      expect(cached?.user).toEqual(mockUser);
      expect(cached?.customPermissions).toEqual(mockCustomPermissions);
      expect(cached?.permissionSets).toEqual(mockPermissionSets);
      expect(cached?.token).toBe(mockToken);
    });

    it('should return null for invalid token', () => {
      const expiresIn = 3600;

      globalPermissionCache.setGlobalCache(
        mockUser,
        mockCustomPermissions,
        mockAbility,
        mockPermissionSets,
        mockToken,
        expiresIn
      );

      const cached = globalPermissionCache.getGlobalCache('different-token');
      expect(cached).toBeNull();
    });

    it('should return null for expired cache', () => {
      const expiresIn = -1; // Already expired

      globalPermissionCache.setGlobalCache(
        mockUser,
        mockCustomPermissions,
        mockAbility,
        mockPermissionSets,
        mockToken,
        expiresIn
      );

      const cached = globalPermissionCache.getGlobalCache(mockToken);
      expect(cached).toBeNull();
    });
  });

  describe('permission check caching', () => {
    it('should cache and retrieve permission check results', () => {
      const cacheKey = 'read:assets:';
      const result = true;

      // Set permission check
      globalPermissionCache.setPermissionCheck(cacheKey, result);

      // Get permission check
      const cached = globalPermissionCache.getPermissionCheck(cacheKey);
      expect(cached).toBe(result);
    });

    it('should return null for non-existent permission check', () => {
      const cached = globalPermissionCache.getPermissionCheck('non-existent');
      expect(cached).toBeNull();
    });

    it('should return null for expired permission check', (done) => {
      const cacheKey = 'read:assets:';
      const result = true;

      // Mock a very short TTL for testing
      const originalTTL = (globalPermissionCache as any).TTL;
      (globalPermissionCache as any).TTL = 1; // 1ms

      globalPermissionCache.setPermissionCheck(cacheKey, result);

      // Wait for expiration
      setTimeout(() => {
        const cached = globalPermissionCache.getPermissionCheck(cacheKey);
        expect(cached).toBeNull();
        
        // Restore original TTL
        (globalPermissionCache as any).TTL = originalTTL;
        done();
      }, 2);
    });
  });

  describe('cache validation', () => {
    it('should validate cache correctly', () => {
      const expiresIn = 3600;

      globalPermissionCache.setGlobalCache(
        mockUser,
        mockCustomPermissions,
        mockAbility,
        mockPermissionSets,
        mockToken,
        expiresIn
      );

      expect(globalPermissionCache.isValid(mockToken)).toBe(true);
      expect(globalPermissionCache.isValid('different-token')).toBe(false);
    });
  });

  describe('cache statistics', () => {
    it('should provide cache statistics', () => {
      const stats = globalPermissionCache.getCacheStats();

      expect(stats).toHaveProperty('hasGlobalCache');
      expect(stats).toHaveProperty('cacheAge');
      expect(stats).toHaveProperty('expiresIn');
      expect(stats).toHaveProperty('permissionChecksCount');
      expect(typeof stats.hasGlobalCache).toBe('boolean');
      expect(typeof stats.permissionChecksCount).toBe('number');
    });

    it('should show correct statistics after caching', () => {
      const expiresIn = 3600;

      globalPermissionCache.setGlobalCache(
        mockUser,
        mockCustomPermissions,
        mockAbility,
        mockPermissionSets,
        mockToken,
        expiresIn
      );

      globalPermissionCache.setPermissionCheck('test:permission', true);

      const stats = globalPermissionCache.getCacheStats();
      expect(stats.hasGlobalCache).toBe(true);
      expect(stats.permissionChecksCount).toBe(1);
      expect(stats.cacheAge).toBeGreaterThan(0);
      expect(stats.expiresIn).toBeGreaterThan(0);
    });
  });

  describe('token update', () => {
    it('should update token in existing cache', () => {
      const expiresIn = 3600;
      const newToken = 'new.jwt.token';
      const newExpiresIn = 7200;

      // Set initial cache
      globalPermissionCache.setGlobalCache(
        mockUser,
        mockCustomPermissions,
        mockAbility,
        mockPermissionSets,
        mockToken,
        expiresIn
      );

      // Update token
      globalPermissionCache.updateToken(newToken, newExpiresIn);

      // Should not be able to get with old token
      expect(globalPermissionCache.getGlobalCache(mockToken)).toBeNull();

      // Should be able to get with new token
      const cached = globalPermissionCache.getGlobalCache(newToken);
      expect(cached).toBeTruthy();
      expect(cached?.token).toBe(newToken);
    });
  });

  describe('clear cache', () => {
    it('should clear all cache data', () => {
      const expiresIn = 3600;

      globalPermissionCache.setGlobalCache(
        mockUser,
        mockCustomPermissions,
        mockAbility,
        mockPermissionSets,
        mockToken,
        expiresIn
      );

      globalPermissionCache.setPermissionCheck('test:permission', true);

      // Verify cache exists
      expect(globalPermissionCache.getGlobalCache(mockToken)).toBeTruthy();
      expect(globalPermissionCache.getPermissionCheck('test:permission')).toBe(true);

      // Clear cache
      globalPermissionCache.clear();

      // Verify cache is cleared
      expect(globalPermissionCache.getGlobalCache(mockToken)).toBeNull();
      expect(globalPermissionCache.getPermissionCheck('test:permission')).toBeNull();

      const stats = globalPermissionCache.getCacheStats();
      expect(stats.hasGlobalCache).toBe(false);
      expect(stats.permissionChecksCount).toBe(0);
    });
  });
});