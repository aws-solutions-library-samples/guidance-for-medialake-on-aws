import { AxiosResponse } from 'axios';

export interface ApiError {
  message: string;
  status?: number;
  code?: string;
}

export interface ApiResponse<T> {
  data: T;
  status: number;
}

export interface QueryConfig {
  [key: string]: string | number | boolean | undefined;
}

export interface CreateConnectorRequest {
  name: string;
  type: string;
  description?: string;
  configuration: Record<string, any>;
}

export interface UpdateConnectorRequest {
  name?: string;
  type?: string;
  description?: string;
  configuration?: Record<string, any>;
}

export interface ConnectorResponse {
  id: string;
  name: string;
  type: string;
  description?: string;
  configuration: Record<string, any>;
  created_at: string;
  updated_at: string;
  createdDate?: string; // Add this for backward compatibility
}

export interface S3ListResponse {
  buckets: string[];
}

// Update Connector interface to match ConnectorResponse
export interface Connector {
  id: string;
  name: string;
  type: string;
  description?: string;
  configuration: Record<string, any>;
  created_at: string;
  updated_at: string;
  createdDate?: string;
}

export type ConnectorListResponse = {
  data: {
    connectors: ConnectorResponse[];
  }
}

export interface Integration {
  id: string;
  type: string;
  apiKey: string;
  name: string;
  createdDate: string;
}

export interface S3BucketResponse {
  buckets: string[];
}
