import { AxiosResponse } from 'axios';

export interface ApiError {
  message: string;
  status?: number;
  code?: string;
}

export interface ApiResponse<T> {
  status: string;
  message: string;
  data: T;
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
  createdAt: string;
  updatedAt: string;
  storageIdentifier: string;
  sqsArn: string;
  region: string;
  configuration?: Record<string, any>;
}

export interface S3ListResponse {
  buckets: string[];
  count: number;
}

export interface S3BucketResponse {
  status: string;
  message: string;
  data: {
    buckets: string[];
  }
}

export interface Connector extends ConnectorResponse {}

export interface ConnectorListResponse {
  status: string;
  message: string;
  data: {
    connectors: ConnectorResponse[];
  }
}

export interface Integration {
  id: string;
  type: string;
  apiKey: string;
  name: string;
  createdAt: string;
}
