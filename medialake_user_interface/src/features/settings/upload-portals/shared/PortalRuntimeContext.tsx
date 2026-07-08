import { createContext, useContext } from "react";

import type { PortalConfig } from "@/features/portal/types/portal.types";

/**
 * Reserved `survey.data` keys used to thread upload state across pages.
 *
 * Both use a double-underscore prefix so they cannot collide with an
 * admin-named metadata field (whose question `name` is the slugified field
 * label). Other modules MUST import these constants instead of hardcoding the
 * string literals so the reserved-key contract stays single-sourced.
 *
 * @see design.md — "Reserved survey keys"
 */
export const SELECTED_DESTINATION_KEY = "__selectedDestinationId";
export const CURRENT_PATH_KEY = "__currentPath";

/**
 * Reserved keys the live uploader writes back into `survey.data` so the
 * survey-level Submit (Complete) handler can finalize the upload session:
 *   - {@link UPLOAD_SESSION_ID_KEY}: the resolved upload sessionId.
 *   - {@link UPLOADED_FILE_COUNT_KEY}: count of successfully uploaded files
 *     (used to true up the session's expectedCount on submit).
 *   - {@link UPLOAD_IN_PROGRESS_KEY}: `true` while an upload is in flight, so
 *     onCompleting can block Submit until uploads settle.
 */
export const UPLOAD_SESSION_ID_KEY = "__uploadSessionId";
export const UPLOADED_FILE_COUNT_KEY = "__uploadedFileCount";
export const UPLOAD_IN_PROGRESS_KEY = "__uploadInProgress";

/**
 * The full set of reserved keys, excluded from {@link collectMetadataValues}.
 * Declared `as const` so the values stay literal-typed for callers.
 */
export const RESERVED_SURVEY_KEYS = [
  SELECTED_DESTINATION_KEY,
  CURRENT_PATH_KEY,
  UPLOAD_SESSION_ID_KEY,
  UPLOADED_FILE_COUNT_KEY,
  UPLOAD_IN_PROGRESS_KEY,
] as const;

/**
 * Runtime context shared with every custom SurveyJS question.
 *
 * SurveyJS instantiates question renderers itself, so the live API surface and
 * cross-page upload state are passed via React context rather than survey
 * props. Both render paths supply a value: the preview renderer uses
 * `mode: "preview"` (mock, non-interactive), the public renderer uses // i18n-ignore
 * `mode: "public"` (live API + Uppy). // i18n-ignore
 *
 * @see design.md — "Custom SurveyJS question contracts"
 */
export interface PortalRuntimeValue {
  /** `"preview"` → mock/non-interactive; `"public"` → live API + Uppy. */
  mode: "preview" | "public";
  /** Portal slug, used by the live uploader/path API calls. */
  slug: string;
  /** Session JWT from the access gate; `null` until a session exists. */
  sessionJwt: string | null;
  /** Public portal config (destinations carry `pageNumber`); `null` until loaded. */
  config: PortalConfig | null;
  /** Called by the destination-selector question when the selection changes. */
  onDestinationChange?: (destinationId: string) => void;
  /** Called by the path questions when the resolved upload path changes. */
  onPathChange?: (path: string) => void;
  /** Called when a live API call reports the session has expired. */
  onSessionExpired?: () => void;
}

/**
 * Default value used when a question renders outside a provider (e.g. an
 * isolated unit test). Defaults to a non-interactive preview with no live
 * session, so nothing attempts a real API call without an explicit provider.
 */
export const DEFAULT_PORTAL_RUNTIME: PortalRuntimeValue = {
  mode: "preview",
  slug: "",
  sessionJwt: null,
  config: null,
};

export const PortalRuntimeContext = createContext<PortalRuntimeValue>(DEFAULT_PORTAL_RUNTIME);

PortalRuntimeContext.displayName = "PortalRuntimeContext";

/** Convenience hook returning the current {@link PortalRuntimeValue}. */
export function usePortalRuntime(): PortalRuntimeValue {
  return useContext(PortalRuntimeContext);
}

/**
 * Minimal structural view of a SurveyJS survey needed by
 * {@link collectMetadataValues}. `survey-core`'s `SurveyModel` is structurally
 * assignable to this shape (its `data` getter returns the answer object), so a
 * real survey instance can be passed directly while tests can pass a plain
 * `{ data }` object without constructing a model. // i18n-ignore
 */
export interface SurveyDataLike {
  /** The SurveyJS answer object: question `name` → value. */
  data: Record<string, unknown>;
}

/**
 * Gather the metadata-field values from a survey's answer object as a
 * `Record<string, string>`, EXCLUDING the reserved keys // i18n-ignore
 * (`__selectedDestinationId`, `__currentPath`).
 *
 * This is the exact shape the existing `getPresignedUrl` call expects for its
 * `metadata` parameter (S3 `x-amz-meta-*` headers are string-valued). Values
 * are serialized to strings:
 *   - arrays (multi-select `checkbox`/`tagbox`) → comma-joined string of their
 *     stringified items, e.g. `["a","b"]` → `"a, b"`; an empty array is skipped; // i18n-ignore
 *   - booleans (`boolean` toggle) → `"true"`/`"false"`;
 *   - plain objects → JSON-stringified (defensive; no current field type emits
 *     an object, but a future structured type would round-trip rather than
 *     surface `"[object Object]"`); // i18n-ignore
 *   - everything else → `String(value)`.
 * `null`/`undefined` answers are skipped so they do not surface as the literal
 * strings `"null"`/`"undefined"`.
 *
 * Pure: depends only on `survey.data`, so it is deterministic and easy to test.
 *
 * @see design.md — Property 9 (metadata contract excludes reserved keys)
 */
export function collectMetadataValues(survey: SurveyDataLike): Record<string, string> {
  const data = survey.data ?? {};
  const reserved = new Set<string>(RESERVED_SURVEY_KEYS);
  const result: Record<string, string> = {};

  for (const [key, value] of Object.entries(data)) {
    if (reserved.has(key)) continue;
    if (value === null || value === undefined) continue;

    if (Array.isArray(value)) {
      // Multi-select (checkbox/tagbox). Skip empties so a touched-but-cleared
      // multi-select doesn't surface as an empty metadata value, and join the
      // stringified items into a single, human-readable header value.
      const items = value
        .filter((item) => item !== null && item !== undefined)
        .map((item) => String(item));
      if (items.length === 0) continue;
      result[key] = items.join(", ");
      continue;
    }

    if (typeof value === "object") {
      // Defensive: no current field type emits an object, but JSON-stringify
      // rather than `String(value)` so a future structured type round-trips
      // instead of collapsing to "[object Object]".
      result[key] = JSON.stringify(value);
      continue;
    }

    result[key] = String(value);
  }

  return result;
}
