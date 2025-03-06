import { test, expect } from '../fixtures/auth-fixture';

/**
 * Test suite for API validation
 */
test.describe('MediaLake API Validation', () => {
  
  test('should get a list of pipelines', async ({ apiClient }) => {
    const response = await apiClient.get('/pipelines');
    const data = await response.json();
    
    expect(response.status()).toBe(200);
    expect(Array.isArray(data.pipelines)).toBeTruthy();
  });
  
  test('should create a new pipeline', async ({ apiClient }) => {
    const pipelineData = {
      name: 'Test Pipeline API',
      description: 'Created via API test',
      nodes: [
        {
          id: 'node1',
          type: 'input',
          position: { x: 100, y: 100 }
        },
        {
          id: 'node2',
          type: 'process',
          position: { x: 300, y: 100 }
        }
      ],
      edges: [
        {
          id: 'edge1',
          source: 'node1',
          target: 'node2'
        }
      ]
    };
    
    const response = await apiClient.post('/pipelines', pipelineData);
    const data = await response.json();
    
    expect(response.status()).toBe(201);
    expect(data.id).toBeDefined();
    expect(data.name).toBe(pipelineData.name);
    
    // Clean up - delete the created pipeline
    const deleteResponse = await apiClient.delete(`/pipelines/${data.id}`);
    expect(deleteResponse.status()).toBe(204);
  });
  
  test('should get pipeline execution history', async ({ apiClient }) => {
    // First, get a list of pipelines to find one to check
    const pipelinesResponse = await apiClient.get('/pipelines');
    const pipelines = await pipelinesResponse.json();
    
    // Skip if no pipelines exist
    test.skip(!pipelines.pipelines.length, 'No pipelines exist to test');
    
    if (pipelines.pipelines.length) {
      const pipelineId = pipelines.pipelines[0].id;
      const response = await apiClient.get(`/pipelines/${pipelineId}/executions`);
      const data = await response.json();
      
      expect(response.status()).toBe(200);
      expect(Array.isArray(data.executions)).toBeTruthy();
    }
  });
  
  test('should get system settings', async ({ apiClient }) => {
    const response = await apiClient.get('/settings');
    const data = await response.json();
    
    expect(response.status()).toBe(200);
    expect(data.settings).toBeDefined();
  });
  
}); 