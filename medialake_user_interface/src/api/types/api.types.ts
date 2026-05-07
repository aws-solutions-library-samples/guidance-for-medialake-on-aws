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
  success: boolean;
  data: T;
  meta?: { timestamp: string; version: string; request_id: string };
  error?: { code: string; message: string; details?: any[] };
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
    allowUploads?: boolean;
    [key: string]: string | string[] | boolean | undefined;
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
  allowUploads?: boolean;
  corsRuleIndex?: number;
  configuration?: {
    queueUrl?: string;
    lambdaArn?: string;
    iamRoleArn?: string;
    objectPrefix?: string | string[];
    allowUploads?: boolean;
    [key: string]: string | string[] | boolean | undefined;
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

/**
 * Response from S3 Explorer API - returns only folder structure (commonPrefixes)
 * Individual file objects are not included to optimize for folder navigation
 */
export interface S3ListObjectsResponse {
  prefix: string;
  delimiter: string;
  commonPrefixes: string[];
  isTruncated: boolean;
  nextContinuationToken?: string;
  allowedPrefixes?: string[];
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

// Portal Types
import type { PortalAppearance } from "@/features/settings/upload-portals/types/appearance.types";

export interface PortalMetadataField {
  label: string;
  type: "text" | "email" | "number" | "select";
  required: boolean;
  order: number;
  options?: string[];
}

export interface PortalPathSegment {
  label: string;
  position: number;
  regex: string;
  segmentType?: "text" | "alphanumeric" | "numbers" | "date" | "list" | "pattern";
  listValues?: string[];
  patternDescription?: string;
}

export interface PortalDestination {
  destinationId: string;
  friendlyName: string;
  connectorId: string;
  rootPath: string;
  allowBrowsing: boolean;
  allowFolderCreation: boolean;
  order: number;
  pathSegments?: PortalPathSegment[];
  pathSeparator?: string;
}

/** Full portal detail — always includes destinations. */
export interface Portal {
  portalId: string;
  slug: string;
  name: string;
  description?: string;
  logoS3Key?: string;
  logoUrl?: string;
  accessMode: "public" | "token-protected" | "cognito-groups";
  allowedGroups?: string[];
  passphrase?: string;
  tokenBypassesPassphrase: boolean;
  ipAllowlist: string[];
  structuredPathMode: boolean;
  isActive: boolean;
  expiresAt?: string;
  maxFileSizeBytes?: number;
  maxFilesPerSession?: number;
  metadataFields: PortalMetadataField[];
  destinations: PortalDestination[];
  captchaEnabled: boolean;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
  /**
   * Visual-editor appearance configuration. Absent on portals saved
   * before the visual editor, in which case consumers deep-merge with
   * `DEFAULT_PORTAL_APPEARANCE`.
   */
  appearance?: PortalAppearance;
  /**
   * Allowed file types for uploads. Empty array means "accept all".
   * Each entry is a MIME pattern (e.g. "image/*") or extension (".pdf").
   */
  allowedFileTypes?: string[];
}

/** List-item shape returned by the list endpoint — destinations may be omitted. */
export interface PortalListItem extends Omit<Portal, "destinations"> {
  destinations?: PortalDestination[];
}

export interface PortalToken {
  tokenId: string;
  associatedEmail: string;
  isRevoked: boolean;
  expiresAt?: string;
  createdAt: string;
  prePopulatedParams?: Record<string, string>;
}

export interface CreatePortalRequest {
  name: string;
  slug: string;
  description?: string;
  accessMode: Portal["accessMode"];
  allowedGroups?: string[];
  passphrase?: string;
  tokenBypassesPassphrase?: boolean;
  ipAllowlist?: string[];
  structuredPathMode?: boolean;
  isActive?: boolean;
  expiresAt?: string;
  maxFileSizeBytes?: number;
  maxFilesPerSession?: number;
  metadataFields?: PortalMetadataField[];
  destinations: PortalDestination[];
  captchaEnabled?: boolean;
  /**
   * Visual-editor appearance configuration. The backend persists this
   * field unchanged alongside the rest of the portal record.
   */
  appearance?: PortalAppearance;
  logoUrl?: string;
  /**
   * Allowed file types for uploads. Empty array means "accept all".
   */
  allowedFileTypes?: string[];
}

export interface UpdatePortalRequest extends Partial<CreatePortalRequest> {}

export interface GenerateTokenRequest {
  associatedEmail: string;
  expiresAt?: string;
  prePopulatedParams?: Record<string, string>;
}

// Backend returns flat arrays/objects in `data`, not nested under keys
export type PortalListResponse = ApiResponse<PortalListItem[]>;
export type PortalResponse = ApiResponse<Portal>;
export type PortalTokenListResponse = ApiResponse<PortalToken[]>;
export type PortalTokenResponse = ApiResponse<{
  tokenId: string;
  associatedEmail: string;
  createdAt: string;
  expiresAt: string;
  isRevoked: boolean;
  rawToken: string;
  shareableUrl: string;
}>;
