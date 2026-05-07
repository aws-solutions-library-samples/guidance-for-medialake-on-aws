import type { PortalAppearance } from "@/features/settings/upload-portals/types/appearance.types";

export interface PortalMetadataField {
  label: string;
  type: "text" | "email" | "number" | "select";
  required: boolean;
  order: number;
  options?: string[];
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
   * Visual-editor appearance configuration. Undefined on portals saved
   * before an appearance was set; the public portal page deep-merges with
   * `DEFAULT_PORTAL_APPEARANCE` in that case so rendering is unchanged.
   */
  appearance?: PortalAppearance;
  /**
   * Allowed file types for uploads. Empty array means "accept all".
   */
  allowedFileTypes?: string[];
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
