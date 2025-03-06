import { test as baseTest, expect } from '@playwright/test';
import { loginUser, logoutUser, getAuthToken } from '../utils/auth';
import { ApiClient } from '../utils/api';

/**
 * Custom fixture that extends the base test with authentication capabilities
 */
export const test = baseTest.extend({
  // Authenticated page fixture
  authenticatedPage: async ({ page }, use) => {
    // Login before the test
    await loginUser(page);
    
    // Use the authenticated page in the test
    await use(page);
    
    // Logout after the test
    await logoutUser(page);
  },
  
  // API client with authentication
  apiClient: async ({ authenticatedPage }, use) => {
    const apiClient = new ApiClient();
    
    // Get auth token from browser and use it for API requests
    const authToken = await getAuthToken(authenticatedPage);
    await apiClient.init(authToken || undefined);
    
    // Use the API client in the test
    await use(apiClient);
    
    // Close the API client after the test
    await apiClient.close();
  },
});

// Export expect for convenience
export { expect }; 