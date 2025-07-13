export interface Connector {
  id: string;
  name: string;
  type: string;
  status: string;
  created_at: string;
  updated_at: string;
  configuration: Record<string, any>;
  storageIdentifier?: string;
  objectPrefix?: string;
}

export interface ConnectorResponse {
  id: string;
  name: string;
  type: string;
  status: string;
  created_at: string;
  updated_at: string;
  configuration: Record<string, any>;
  storageIdentifier?: string;
  objectPrefix?: string;
}
