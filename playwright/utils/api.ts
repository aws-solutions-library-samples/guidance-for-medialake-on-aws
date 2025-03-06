import { APIRequestContext, APIResponse, request } from '@playwright/test';

/**
 * Base API client for making requests to the API
 */
export class ApiClient {
  private context: APIRequestContext;
  private baseUrl: string;
  private authToken: string | null = null;
  
  constructor(baseUrl: string = process.env.API_URL || 'https://api.example.com') {
    this.baseUrl = baseUrl;
  }

  /**
   * Initialize the API context with authentication
   */
  async init(authToken?: string): Promise<void> {
    this.authToken = authToken || null;
    this.context = await request.newContext({
      baseURL: this.baseUrl,
      extraHTTPHeaders: this.authToken 
        ? { 'Authorization': `Bearer ${this.authToken}` }
        : {},
    });
  }

  /**
   * Performs a GET request to the API
   */
  async get(path: string): Promise<APIResponse> {
    return await this.context.get(path);
  }

  /**
   * Performs a POST request to the API
   */
  async post(path: string, data: any): Promise<APIResponse> {
    return await this.context.post(path, {
      data,
    });
  }

  /**
   * Performs a PUT request to the API
   */
  async put(path: string, data: any): Promise<APIResponse> {
    return await this.context.put(path, {
      data,
    });
  }

  /**
   * Performs a DELETE request to the API
   */
  async delete(path: string): Promise<APIResponse> {
    return await this.context.delete(path);
  }

  /**
   * Closes the API context
   */
  async close(): Promise<void> {
    await this.context.dispose();
  }
}

/**
 * Helper to check if the CDK stack is deployed
 */
export async function isStackDeployed(
  stackName: string, 
  region: string = process.env.AWS_REGION || 'us-east-1'
): Promise<boolean> {
  // This would typically use the AWS SDK but for testing purposes we'll use a simple API check
  const apiClient = new ApiClient();
  await apiClient.init();
  
  try {
    // This endpoint would be implemented to check stack status - example placeholder
    const response = await apiClient.get(`/stacks/${stackName}?region=${region}`);
    const json = await response.json();
    await apiClient.close();
    
    return json.status === 'COMPLETE';
  } catch (error) {
    await apiClient.close();
    return false;
  }
} 