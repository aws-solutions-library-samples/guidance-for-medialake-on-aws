import { APIRequestContext, request } from '@playwright/test';

export class ApiClient {
  private context: APIRequestContext;
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  /**
   * Initialize the API client
   */
  async init(): Promise<void> {
    this.context = await request.newContext({
      baseURL: this.baseUrl,
      extraHTTPHeaders: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
    });
  }

  /**
   * Set the authentication token for subsequent requests
   * @param token Auth token
   */
  setToken(token: string): void {
    this.token = token;
  }

  /**
   * Make a GET request to the API
   * @param endpoint API endpoint
   * @returns Response data
   */
  async get<T>(endpoint: string): Promise<T> {
    const headers: Record<string, string> = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await this.context.get(endpoint, { headers });
    return await response.json() as T;
  }

  /**
   * Make a POST request to the API
   * @param endpoint API endpoint
   * @param data Request payload
   * @returns Response data
   */
  async post<T>(endpoint: string, data: any): Promise<T> {
    const headers: Record<string, string> = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await this.context.post(endpoint, {
      headers,
      data,
    });
    return await response.json() as T;
  }

  /**
   * Make a PUT request to the API
   * @param endpoint API endpoint
   * @param data Request payload
   * @returns Response data
   */
  async put<T>(endpoint: string, data: any): Promise<T> {
    const headers: Record<string, string> = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await this.context.put(endpoint, {
      headers,
      data,
    });
    return await response.json() as T;
  }

  /**
   * Make a DELETE request to the API
   * @param endpoint API endpoint
   * @returns Response data
   */
  async delete<T>(endpoint: string): Promise<T> {
    const headers: Record<string, string> = {};
    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    const response = await this.context.delete(endpoint, { headers });
    return await response.json() as T;
  }

  /**
   * Dispose of the API client
   */
  async dispose(): Promise<void> {
    await this.context.dispose();
  }
} 