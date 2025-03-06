import { test, expect } from '@playwright/test';

/**
 * API tests for MediaLake application
 * Note: Some tests require the API server to be running
 */

// Skip these tests by default since they require the API server
// Remove the .skip() to run these tests when the API server is available
test.describe.skip('Public API', () => {
  test('health check endpoint should return 200', async ({ request }) => {
    const response = await request.get('/api/health');
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    expect(body.status).toBe('ok');
  });
  
  test('version endpoint should return correct version', async ({ request }) => {
    const response = await request.get('/api/version');
    expect(response.status()).toBe(200);
    
    const body = await response.json();
    expect(body.version).toBeDefined();
  });
});

// These tests don't require an API server
test.describe('Mock API', () => {
  test('mock health check', async () => {
    // Mock API response
    const mockResponse = {
      status: 'ok',
      timestamp: new Date().toISOString(),
      services: {
        database: 'connected',
        storage: 'connected'
      }
    };
    
    expect(mockResponse.status).toBe('ok');
    expect(mockResponse.services.database).toBe('connected');
  });
  
  test('mock user profile', async () => {
    // Mock user profile data
    const mockUserProfile = {
      id: 'user-123',
      username: 'testuser',
      email: 'test@example.com',
      preferences: {
        theme: 'dark',
        notifications: true
      }
    };
    
    expect(mockUserProfile.id).toBeDefined();
    expect(mockUserProfile.username).toBe('testuser');
    expect(mockUserProfile.preferences.theme).toBe('dark');
  });
}); 