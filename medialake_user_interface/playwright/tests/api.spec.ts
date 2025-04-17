import { test, expect } from '../fixtures/auth-fixture';

/**
 * API tests for MediaLake application
 */
test.describe('MediaLake API', () => {
  
  test('should fetch user profile with authentication', async ({ apiClient }) => {
    const response = await apiClient.get('/user/profile');
    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data.id).toBeDefined();
    expect(data.email).toBeDefined();
  });
  
  test('should fetch pipelines with authentication', async ({ apiClient }) => {
    const response = await apiClient.get('/pipelines');
    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(Array.isArray(data)).toBeTruthy();
  });
  
  test('should create a pipeline with authentication', async ({ apiClient }) => {
    const pipelineData = {
      name: 'Test Pipeline',
      description: 'Created by Playwright test',
      settings: {
        input: 's3://test-bucket/input',
        output: 's3://test-bucket/output'
      }
    };
    
    const response = await apiClient.post('/pipelines', pipelineData);
    expect(response.status()).toBe(201);
    
    const data = await response.json();
    expect(data.id).toBeDefined();
    expect(data.name).toBe(pipelineData.name);
  });
  
  // Public API tests
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
