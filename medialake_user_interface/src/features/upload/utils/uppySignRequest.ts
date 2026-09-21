/**
 * Glue between Uppy 6's `@uppy/aws-s3` `signRequest` callback and MediaLake's presign APIs.
 *
 * Uppy performs every S3 request itself and asks `signRequest({ method, key, uploadId?,
 * partNumber? })` for one presigned URL per request. It hands over no file object, so the
 * pieces here recover the file (and therefore the destination) from the request:
 *
 * - `generateObjectKey` returns `file.id`, so the *create* request (no `uploadId`) arrives
 *   with the Uppy file id as its key and the file can be looked up directly.
 * - The server answers the create request with its own key. It is stamped onto
 *   `file.meta` (`s3Key`, `s3Bucket`, `s3ConnectorId`), and the plugin persists
 *   `file.s3Multipart = { uploadId, key }` for multipart uploads. Every later request
 *   arrives with that server key, and `findFileForS3Key` maps it back to the file — also
 *   after a Golden Retriever restore, when in-memory maps are gone but file meta and
 *   `s3Multipart` state have been restored from IndexedDB.
 */
import type { Body, Meta, Uppy, UppyFile } from "@uppy/core";
import type { MultipartSignOperation, UploadCreateMethod } from "../types/upload.types";

/** The request object Uppy passes to `signRequest`. */
export interface SignRequestInput {
  method: "PUT" | "POST" | "GET" | "DELETE";
  key: string;
  uploadId?: string;
  partNumber?: number;
  expiresIn?: number;
}

/** What `signRequest` must resolve with. `key` only on the create request. */
export interface SignRequestResult {
  url: string;
  key?: string;
}

/** Keys stamped onto `file.meta` once the server has chosen the object key. */
export const S3_META_KEY = "s3Key";
export const S3_META_BUCKET = "s3Bucket";
export const S3_META_CONNECTOR_ID = "s3ConnectorId";

/** Files above this go multipart; matches the server's size-based default. */
export const MULTIPART_THRESHOLD_BYTES = 100 * 1024 * 1024;

/** How long Golden Retriever keeps a recoverable upload; matches the directive-row TTL. */
export const GOLDEN_RETRIEVER_EXPIRES_MS = 7 * 24 * 60 * 60 * 1000;

/**
 * Part size scaled with file size to keep the number of parts (and sign round-trips)
 * manageable while respecting S3's 5 MiB minimum and 10,000-part maximum.
 */
export function getChunkSize(file: { size: number | null }): number {
  const GB = 1024 * 1024 * 1024;
  const MB = 1024 * 1024;
  const size = file.size ?? 0;
  if (size >= 100 * GB) return 500 * MB;
  if (size >= 10 * GB) return 200 * MB;
  if (size >= 1 * GB) return 100 * MB;
  if (size >= 100 * MB) return 50 * MB;
  return 5 * MB;
}

/** The content type Uppy will put in the `Content-Type` header — sign exactly this. */
export function contentTypeForSigning(file: { type?: string | null }): string {
  return file.type || "application/octet-stream";
}

/** True for the request that creates the object (PUT, or POST without an upload id). */
export function isCreateRequest(request: SignRequestInput): boolean {
  return !request.uploadId;
}

export function createMethodOf(request: SignRequestInput): UploadCreateMethod {
  if (request.method !== "PUT" && request.method !== "POST") {
    throw new Error(`Unexpected create method ${request.method} for key ${request.key}`);
  }
  return request.method;
}

/** Map a multipart request to the server-side sign operation. */
export function multipartOperationOf(request: SignRequestInput): MultipartSignOperation {
  switch (request.method) {
    case "GET":
      return "list";
    case "DELETE":
      return "abort";
    case "PUT":
      return "part";
    case "POST":
      return "complete";
    default:
      throw new Error(`Unexpected multipart method ${String(request.method)}`);
  }
}

/**
 * The Uppy file whose object key is `key` — by the server key stamped on its meta, by the
 * multipart state the plugin persists, or (for the create request) by file id.
 */
export function findFileForS3Key<M extends Meta, B extends Body>(
  uppy: Uppy<M, B>,
  key: string
): UppyFile<M, B> | undefined {
  const byId = uppy.getFile(key);
  if (byId) return byId;
  return uppy.getFiles().find((file) => {
    const meta = file.meta as Record<string, unknown>;
    const multipart = (file as { s3Multipart?: { key?: string } }).s3Multipart;
    return meta[S3_META_KEY] === key || multipart?.key === key;
  });
}

/** Record the server's decision on the file so later requests can be routed. */
export function stampS3Meta<M extends Meta, B extends Body>(
  uppy: Uppy<M, B>,
  fileId: string,
  values: { key: string; bucket: string; connectorId?: string }
): void {
  const meta: Record<string, string> = {
    [S3_META_KEY]: values.key,
    [S3_META_BUCKET]: values.bucket,
  };
  if (values.connectorId) meta[S3_META_CONNECTOR_ID] = values.connectorId;
  uppy.setFileMeta(fileId, meta as unknown as M);
}

/**
 * Register the Golden Retriever service worker so files larger than IndexedDB's per-file
 * budget survive a refresh. Optional: without it, state and small files still restore from
 * IndexedDB and larger files show as ghosts to re-select. Module service workers are not
 * supported everywhere (notably Firefox), so failure is logged and swallowed.
 */
export async function registerGoldenRetrieverServiceWorker(
  scriptUrl = "/sw.js"
): Promise<ServiceWorkerRegistration | null> {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return null;
  try {
    return await navigator.serviceWorker.register(scriptUrl, { type: "module" });
  } catch (error) {
    console.warn("Golden Retriever service worker registration failed:", error);
    return null;
  }
}
