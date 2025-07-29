export interface UserAttributes {
  email: string;
  email_verified: string;
  given_name: string;
  family_name: string;
  sub: string;
}

export interface User {
  username: string;
  email: string;
  enabled: boolean;
  status: string;
  created: string;
  modified: string;
  email_verified: string;
  given_name: string | null;
  family_name: string | null;
  name?: string;
  groups: string[];
  permissions?: string[];
}

export interface CreateUserRequest {
  username: string;
  email: string;
  enabled?: boolean;
  groups?: string[];
  permissions?: string[];
  given_name?: string;
  family_name?: string;
}

export interface CreateUserResponse {
  status: number;
  message: string;
  data: {
    username: string;
    userStatus: string;
    groupsAdded: string[];
    groupsFailed?: Array<{
      group_id: string;
      error_code: string;
      error_message: string;
    }>;
    groupsFailedCount?: number;
    invalidGroups?: string[];
    invalidGroupsCount?: number;
  };
}

export interface UpdateUserRequest {
  username: string;
  email?: string;
  enabled?: boolean;
  groups?: string[];
  permissions?: string[];
  given_name?: string;
  family_name?: string;
}

export interface ToggleUserStatusRequest {
  username: string;
  enabled: boolean;
}

export interface Role {
  id: string;
  name: string;
  description: string;
  permissions: string[];
  createdAt?: string;
  updatedAt?: string;
}

export interface CreateRoleRequest {
  name: string;
  description: string;
  permissions: string[];
}

export interface UpdateRoleRequest {
  name?: string;
  description?: string;
  permissions?: string[];
}

export interface RoleListResponse {
  status: string;
  message: string;
  data: {
    roles: Role[];
  };
}

export interface RoleResponse {
  status: string;
  message: string;
  data: {
    role: Role;
  };
}

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
  configuration: {
    connectorType?: string;
    bucket?: string;
    s3IntegrationMethod?: "s3Notifications" | "eventbridge";
    region?: string;
    objectPrefix?: string | string[];
    [key: string]: string | string[] | undefined;
  };
}

export interface UpdateConnectorRequest {
  name?: string;
  type?: string;
  description?: string;
  configuration?: Record<string, any>;
}

export interface ConnectorUsage {
  used: number;
  total: number;
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
  status?: string;
  integrationMethod?: string;
  objectPrefix?: string | string[];
  usage?: {
    total: number;
  };
  description?: string;
  iamRoleArn?: string;
  lambdaArn?: string;
  queueUrl?: string;
  configuration?: {
    queueUrl?: string;
    lambdaArn?: string;
    iamRoleArn?: string;
    objectPrefix?: string | string[];
    [key: string]: string | string[] | undefined;
  };
  settings?: {
    bucket: string;
    region?: string;
    path?: string;
  };
}

export interface ConnectorsListResponse {
  status: string;
  message: string;
  data: {
    connectors: ConnectorResponse[];
  };
}

export interface SingleConnectorResponse {
  status: number;
  message: string;
  data: ConnectorResponse;
}

// export interface ConnectorResponse {
//   id: string;
//   name: string;
//   type: string;
//   description?: string;
//   createdAt: string;
//   updatedAt: string;
//   storageIdentifier: string;
//   sqsArn: string;
//   region: string;
//   integrationMethod?: string;
//   iamRoleArn?: string;
//   lambdaArn?: string;
//   queueUrl?: string;
//   configuration?: {
//     queueUrl?: string;
//     lambdaArn?: string;
//     iamRoleArn?: string;
//   } & Record<string, any>;
//   usage?: {
//     total: number;
//   };
//   settings?: {
//     bucket: string;
//     region?: string;
//     path?: string;
//   };
//   status?: string;
// }
export interface S3ListResponse {
  buckets: string[];
  count: number;
}

export interface S3BucketResponse {
  status: string;
  message: string;
  data: {
    buckets: string[];
  };
}

export interface S3Object {
  Key: string;
  LastModified: string;
  ETag: string;
  Size: number;
  StorageClass: string;
  IsFolder?: boolean;
}

export interface S3ListObjectsResponse {
  objects: S3Object[];
  prefix: string;
  delimiter: string;
  commonPrefixes: string[];
  isTruncated: boolean;
  nextContinuationToken?: string;
}

export interface Connector extends ConnectorResponse {}

export interface ConnectorListResponse {
  status: string;
  message: string;
  data: {
    connectors: ConnectorResponse[];
  };
}

export interface Integration {
  id: string;
  type: string;
  apiKey: string;
  name: string;
  createdAt: string;
}

export interface UserListResponse {
  status: string;
  message: string;
  data: {
    users: User[];
  };
}

export interface UserResponse {
  status: string;
  message: string;
  data: {
    user: User;
  };
}

// AWS Specific Types
export interface AWSRegion {
  value: string;
  label: string;
}
