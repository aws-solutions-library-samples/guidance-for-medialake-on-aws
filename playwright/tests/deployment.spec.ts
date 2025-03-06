import { test, expect } from '@playwright/test';
import { isStackDeployed } from '../utils/api';

/**
 * Test suite for validating CDK deployment statuses
 */
test.describe('CDK Deployment Validation', () => {
  
  test('should verify base infrastructure stack is deployed', async () => {
    // Replace with your actual stack name
    const isDeployed = await isStackDeployed('MediaLakeBaseInfrastructureStack');
    expect(isDeployed).toBeTruthy();
  });
  
  test('should verify API Gateway stack is deployed', async () => {
    // Replace with your actual stack name
    const isDeployed = await isStackDeployed('MediaLakeApiGatewayStack');
    expect(isDeployed).toBeTruthy();
  });
  
  test('should verify Pipeline stack is deployed', async () => {
    // Replace with your actual stack name
    const isDeployed = await isStackDeployed('MediaLakePipelineStack');
    expect(isDeployed).toBeTruthy();
  });
  
  test('should verify User Interface stack is deployed', async () => {
    // Replace with your actual stack name
    const isDeployed = await isStackDeployed('MediaLakeUserInterfaceStack');
    expect(isDeployed).toBeTruthy();
  });
  
}); 