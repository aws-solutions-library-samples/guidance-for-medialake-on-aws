import { test as base } from '@playwright/test';
import { login, logout } from '../utils/auth';
import { ApiClient } from '../utils/api';

// Test fixtures interface
type AuthFixtures = {
  loggedInPage: {
    page: any;
    username: string;
  };
  apiClient: ApiClient;
};

// Test with authentication
export const test = base.extend<AuthFixtures>({
  // Logged in page fixture
  loggedInPage: async ({ page }, use) => {
    // Get credentials from environment or use defaults
    const username = process.env.TEST_USERNAME || 'test@example.com';
    const password = process.env.TEST_PASSWORD || 'Password123!';
    
    // Login
    await login(page, username, password);
    
    // Use the authenticated page
    await use({ page, username });
    
    // Cleanup: logout
    await logout(page);
  },
  
  // API client fixture
  apiClient: async ({}, use) => {
    // Get API URL from environment or use default
    const apiUrl = process.env.API_URL || 'https://api.example.com';
    
    // Create API client
    const client = new ApiClient(apiUrl);
    await client.init();
    
    // Use the API client
    await use(client);
    
    // Cleanup: dispose of client
    await client.dispose();
  },
}); 