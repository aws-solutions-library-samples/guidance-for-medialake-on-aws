import { test, expect } from '@playwright/test';
import { test as authTest } from './fixtures/auth-fixture';

// Public API tests
test.describe('Public API', () => {
  test('health check endpoint should return 200', async ({ request }) => {
    const response = await request.get('/api/health');
    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data.status).toBe('ok');
  });
  
  test('version endpoint should return correct version', async ({ request }) => {
    const response = await request.get('/api/version');
    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data.version).toBeTruthy();
  });
});

// Authenticated API tests
authTest.describe('Authenticated API', () => {
  authTest('user profile endpoint should return user data', async ({ apiClient }) => {
    const data = await apiClient.get('/api/profile');
    
    expect(data).toBeDefined();
    expect(data.email).toBeTruthy();
    expect(data.id).toBeTruthy();
  });
  
  authTest('should be able to update user preferences', async ({ apiClient }) => {
    const preferences = { theme: 'dark', notifications: true };
    
    const data = await apiClient.put('/api/profile/preferences', preferences);
    
    expect(data).toBeDefined();
    expect(data.success).toBe(true);
    
    // Verify preferences were updated
    const profile = await apiClient.get('/api/profile');
    expect(profile.preferences.theme).toBe('dark');
    expect(profile.preferences.notifications).toBe(true);
  });
}); 