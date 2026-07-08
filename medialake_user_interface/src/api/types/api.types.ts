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
  type: "text" | "number" | "select" | "radiogroup" | "checkbox" | "tagbox" | "boolean";
  required: boolean;
  order: number;
  options?: string[];
  /**
   * 1-based page this field renders on. Undefined on portals saved before
   * multi-page support; such portals are treated as a single page.
   */
  pageNumber?: number;
  /**
   * Optional automation role. Absent (or `"none"`) = plain data field. When
   * `"collection-picker"`, the field's value is interpreted by the BACKEND at
   * upload time as a set of collection IDs to add the uploaded asset to
   * (validated against {@link PortalMetadataFieldRoleConfig.allowedCollectionIds}).
   * The form renderer never reads this — it only renders `type`.
   *
   * @see portal-metadata-automation-design.md (Layer A — semantic roles).
   */
  role?: "none" | "collection-picker";
  /**
   * Role-specific configuration. For `role: "collection-picker"`:
   *   - `allowedCollections`: the admin-curated allow-list the end user may
   *     pick from. Stored as `{ id, name }` pairs so the public renderer can
   *     show friendly collection names as choices while the value is the id.
   *     This is the server-validated allow-list.
   *   - `fixedCollectionIds`: collections every upload through this portal joins
   *     regardless of the user's choice (ids only; no display needed).
   *   - `multiple`: when true the picker is multi-select (tagbox); otherwise a
   *     single-select dropdown.
   */
  roleConfig?: {
    allowedCollections?: { id: string; name: string }[];
    fixedCollectionIds?: string[];
    multiple?: boolean;
  };
}

/**
 * Ordered element placement on a {@link PortalPage}. Discriminated on `kind`:
 * a `metadata-field` element references a metadata field by `fieldKey`; the
 * other kinds map to the built-in destination selector, path questions, and
 * uploader question types.
 */
export type PortalPageElement =
  | { kind: "metadata-field"; fieldKey: string }
  | { kind: "destination-selector" }
  | { kind: "path-browser" }
  | { kind: "path-builder" }
  | { kind: "uploader" };

/**
 * A single page in a multi-page portal flow. The persisted `pages` array is
 * the source of truth for structure; the SurveyJS schema is derived from it
 * at render time.
 */
export interface PortalPage {
  /** 1-based, contiguous. Page navigation order. */
  pageNumber: number;
  /** Admin-facing page title (rendered as the SurveyJS page title). */
  title: string;
  /** Optional rich description (sanitized HTML). */
  descriptionHtml?: string;
  /** Ordered element placement on this page. */
  elements: PortalPageElement[];
  /** Optional SurveyJS visibleIf expression for conditional page display. */
  visibleIf?: string;
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
  /**
   * 1-based page whose destination-selector offers this destination.
   * Undefined on portals saved before multi-page support.
   */
  pageNumber?: number;
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
  /**
   * When true (default), the portal shows a Submit step; clicking it marks the
   * session submitted (drives the formSubmissionComplete signal). When false,
   * the portal is upload-only and formSubmissionComplete is always false.
   */
  formSubmissionEnabled: boolean;
  createdBy: string;
  createdAt: string;
  updatedAt: string;
  /**
   * Ordered pages composing the multi-page portal flow. The source of truth
   * for structure; the SurveyJS schema is derived from it at render time.
   */
  pages: PortalPage[];
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
  /**
   * Optional automation tag used to route upload-batch completion events
   * to a trigger pipeline node. Set by the administrator in the portal editor.
   */
  automationTag?: string;
  /**
   * The theme this portal was created from. Informational only — there is
   * no live link, so editing the referenced theme does NOT change this
   * portal's appearance (appearance is snapshot/copied at create time).
   */
  themeId?: string;
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
  /** When true (default), show a Submit step; false = upload-only portal. */
  formSubmissionEnabled?: boolean;
  /**
   * Ordered pages composing the multi-page portal flow. Required on create;
   * `UpdatePortalRequest` makes it optional (omitting leaves pages unchanged).
   */
  pages: PortalPage[];
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
  /**
   * Optional automation tag for routing upload-batch completion events.
   */
  automationTag?: string;
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

// Portal Themes & Templates ---------------------------------------------------
//
// Themes (appearance only) and Templates (full structure snapshot) are two
// separate reusable entities. Creation from either is snapshot/copy-on-create
// (no live inheritance): a portal's `themeId`/`templateId` references are
// informational only. Themes are served by `/settings/portal-themes` and
// templates by `/settings/portal-templates`.

/**
 * A reusable appearance-only theme. Mirrors the backend `PortalThemeModel`.
 * List responses omit `appearance`; the single-get response includes it.
 */
export interface PortalTheme {
  themeId: string;
  name: string;
  description?: string;
  /**
   * Appearance snapshot. Present on the single-theme get; omitted from list
   * items (which return identity + timestamps only).
   */
  appearance?: PortalAppearance;
  createdBy?: string;
  createdAt?: string;
  updatedAt?: string;
}

/** Request body for `POST /settings/portal-themes`. */
export interface CreatePortalThemeRequest {
  name: string;
  description?: string;
  appearance?: PortalAppearance;
}

/** Request body for `PUT /settings/portal-themes/{id}`. */
export interface UpdatePortalThemeRequest extends Partial<CreatePortalThemeRequest> {}

/**
 * A reusable full-structure template. Mirrors the backend `PortalTemplateModel`
 * snapshot — the same shapes as a portal record, minus any passphrase
 * (templates NEVER store a passphrase). List responses return identity +
 * `themeId` + timestamps only; the single-get response includes the full
 * structure snapshot.
 */
export interface PortalTemplate {
  templateId: string;
  name: string;
  description?: string;
  /** Optional bundled theme reference (informational; copied on create). */
  themeId?: string;
  /** Structure snapshot — present on the single-template get. */
  pages?: PortalPage[];
  metadataFields?: PortalMetadataField[];
  /** Destinations carry `connectorId` + `pageNumber` verbatim. */
  destinations?: PortalDestination[];
  appearance?: PortalAppearance;
  accessMode?: Portal["accessMode"];
  allowedGroups?: string[];
  ipAllowlist?: string[];
  tokenBypassesPassphrase?: boolean;
  structuredPathMode?: boolean;
  captchaEnabled?: boolean;
  formSubmissionEnabled?: boolean;
  maxFileSizeBytes?: number;
  maxFilesPerSession?: number;
  createdBy?: string;
  createdAt?: string;
  updatedAt?: string;
}

/**
 * Request body for `POST /settings/portal-templates`. A full structure
 * snapshot of a portal config — NO passphrase (templates never carry one).
 */
export interface CreatePortalTemplateRequest {
  name: string;
  description?: string;
  themeId?: string;
  pages: PortalPage[];
  metadataFields?: PortalMetadataField[];
  destinations: PortalDestination[];
  appearance?: PortalAppearance;
  accessMode?: Portal["accessMode"];
  allowedGroups?: string[];
  ipAllowlist?: string[];
  tokenBypassesPassphrase?: boolean;
  structuredPathMode?: boolean;
  captchaEnabled?: boolean;
  formSubmissionEnabled?: boolean;
  maxFileSizeBytes?: number;
  maxFilesPerSession?: number;
}

/** Request body for `PUT /settings/portal-templates/{id}`. */
export interface UpdatePortalTemplateRequest extends Partial<CreatePortalTemplateRequest> {}

// Backend returns flat arrays/objects in `data`, mirroring the portal wrappers.
export type PortalThemeListResponse = ApiResponse<PortalTheme[]>;
export type PortalThemeResponse = ApiResponse<PortalTheme>;
export type PortalTemplateListResponse = ApiResponse<PortalTemplate[]>;
export type PortalTemplateResponse = ApiResponse<PortalTemplate>;
