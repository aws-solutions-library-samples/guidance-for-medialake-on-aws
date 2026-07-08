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
   * Optional automation role (see api.types.ts `PortalMetadataField.role`).
   * `"collection-picker"` makes the field's value a server-interpreted set of
   * collection IDs to add the uploaded asset to. The renderer ignores this.
   */
  role?: "none" | "collection-picker";
  /** Role-specific config; for `collection-picker` see api.types.ts. */
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

export interface PathSegmentRule {
  label: string;
  position: number;
  regex: string;
}

/** User-friendly segment type that maps to a regex pattern behind the scenes. */
export type PathSegmentType = "text" | "alphanumeric" | "numbers" | "date" | "list" | "pattern";

/** Extended segment rule with user-friendly metadata stored alongside the regex. */
export interface PathSegmentRuleExtended extends PathSegmentRule {
  /** Stable unique identifier for React reconciliation during reorder. */
  id: string;
  /** The user-friendly type selection. Used by the Rule Builder UI. */
  segmentType?: PathSegmentType;
  /** Allowed values when segmentType is "list". */
  listValues?: string[];
  /** Human-readable pattern description when segmentType is "pattern". */
  patternDescription?: string;
  /** Whether this segment is required. Defaults to true. */
  required?: boolean;
}

export interface PortalDestination {
  destinationId: string;
  friendlyName: string;
  rootPath?: string;
  allowBrowsing: boolean;
  allowFolderCreation: boolean;
  order: number;
  pathSegments?: PathSegmentRule[] | null;
  pathSeparator?: string;
  /**
   * 1-based page whose destination-selector offers this destination.
   * Undefined on portals saved before multi-page support.
   */
  pageNumber?: number;
}

export interface PortalConfig {
  slug: string;
  name: string;
  description?: string;
  logoUrl?: string;
  accessMode: "public" | "token-protected" | "cognito-groups";
  tokenBypassesPassphrase: boolean;
  isActive: boolean;
  expiresAt?: string;
  maxFileSizeBytes?: number;
  maxFilesPerSession?: number;
  metadataFields: PortalMetadataField[];
  destinations: PortalDestination[];
  structuredPathMode: boolean;
  captchaEnabled: boolean;
  /**
   * When true (default), the portal shows a Submit step whose click marks the
   * session submitted. When false, the portal is upload-only (no Submit button).
   */
  formSubmissionEnabled?: boolean;
  /**
   * Ordered pages composing the multi-page portal flow. The source of truth
   * for structure; the SurveyJS schema is derived from it at render time.
   */
  pages: PortalPage[];
  /**
   * Visual-editor appearance configuration. Undefined on portals saved
   * before an appearance was set; the public portal page deep-merges with
   * `DEFAULT_PORTAL_APPEARANCE` in that case so rendering is unchanged.
   */
  appearance?: PortalAppearance;
  /**
   * Allowed file types for uploads. Empty array means "accept all".
   */
  allowedFileTypes?: string[];
  /**
   * The theme this portal was created from. Informational only — there is
   * no live link, so editing the referenced theme does NOT change this
   * portal's appearance (appearance is snapshot/copied at create time).
   */
  themeId?: string;
}

export type PortalAuthCredentials =
  | Record<string, never>
  | { token: string; email: string }
  | { passphrase: string }
  | { token: string; email: string; passphrase: string };

export interface ConflictResolutionResult {
  action: "overwrite" | "skip";
  applyToAll: boolean;
}

export interface PortalSessionState {
  sessionJwt: string | null;
  portalConfig: PortalConfig | null;
  accessGateState: "loading" | "gate" | "authenticated";
}

export interface PortalAuthResponse {
  sessionToken: string;
  accessMode: "public" | "token-protected" | "cognito-groups";
}

export interface PortalMultipartMetadata {
  uploadId: string;
  key: string;
  bucket: string;
}
