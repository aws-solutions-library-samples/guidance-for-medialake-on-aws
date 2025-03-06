import { test, expect } from '@playwright/test';
import { ApiClient } from '../utils/api';

/**
 * Test suite for validating CDK stack outputs and resources
 */
test.describe('CDK Stack Outputs and Resources', () => {
  let apiClient: ApiClient;
  
  test.beforeAll(async () => {
    apiClient = new ApiClient();
    await apiClient.init();
  });
  
  test.afterAll(async () => {
    await apiClient.close();
  });
  
  test('should verify API Gateway endpoint is accessible', async () => {
    // This would be retrieved from CDK output or environment variable in real scenario
    const apiEndpoint = process.env.API_ENDPOINT || 'https://example-api.com';
    
    // Create a new ApiClient with the stack output endpoint
    const stackApiClient = new ApiClient(apiEndpoint);
    await stackApiClient.init();
    
    // Test a basic health endpoint
    const response = await stackApiClient.get('/health');
    expect(response.status()).toBe(200);
    
    await stackApiClient.close();
  });
  
  test('should verify S3 bucket is accessible', async () => {
    // This endpoint would be implemented to test S3 access - example placeholder
    const response = await apiClient.get('/storage/health');
    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data.status).toBe('healthy');
    expect(data.bucketExists).toBeTruthy();
  });
  
  test('should verify Lambda functions are deployed', async () => {
    // This endpoint would be implemented to check Lambda functions status - example placeholder
    const response = await apiClient.get('/lambdas/status');
    expect(response.status()).toBe(200);
    
    const data = await response.json();
    
    // Verify key Lambda functions exist
    expect(data.lambdas.find((l: any) => l.name.includes('pipeline-executor'))).toBeDefined();
    expect(data.lambdas.find((l: any) => l.name.includes('asset-processor'))).toBeDefined();
    expect(data.lambdas.find((l: any) => l.name.includes('auth-handler'))).toBeDefined();
  });
  
  test('should verify Cognito user pool is configured', async () => {
    // This endpoint would be implemented to check Cognito configuration - example placeholder
    const response = await apiClient.get('/auth/config');
    expect(response.status()).toBe(200);
    
    const data = await response.json();
    expect(data.userPoolId).toBeDefined();
    expect(data.clientId).toBeDefined();
  });
  
}); 