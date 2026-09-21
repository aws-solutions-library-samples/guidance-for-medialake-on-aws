export interface Connector {
  id: string;
  name: string;
  description?: string;
  type: string;
  storageIdentifier: string;
  region: string;
  objectPrefix?: string;
  status: string;
}

/**
 * Which S3 request the browser is about to make for a new object, mirroring the ``method``
 * Uppy's ``signRequest`` receives: ``PUT`` writes the object in one request, ``POST``
 * (without an upload id) creates a multipart upload.
 */
export type UploadCreateMethod = "PUT" | "POST";

/** Request body for ``POST /assets/upload`` — sign the request that creates the object. */
export interface CreateUploadRequest {
  connector_id: string;
  filename: string;
  content_type: string;
  file_size: number;
  path?: string;
  collection_ids?: string[];
  method: UploadCreateMethod;
}

/**
 * Response of ``POST /assets/upload``.
 *
 * ``key`` is authoritative: the client proposed a placeholder and must use this key for the
 * rest of the upload. ``url`` is a presigned PutObject (``PUT``) or CreateMultipartUpload
 * (``POST``); the browser talks to S3 directly from here on.
 */
export interface CreateUploadResponse {
  bucket: string;
  key: string;
  url: string;
  method: UploadCreateMethod;
  multipart: boolean;
  expires_in: number;
}

/** One S3 request of an in-flight multipart upload that the server presigns. */
export type MultipartSignOperation = "part" | "list" | "complete" | "abort";

export interface SignMultipartRequest {
  connector_id: string;
  upload_id: string;
  key: string;
  operation: MultipartSignOperation;
  /** Required for ``part``. */
  part_number?: number;
}

export interface SignMultipartResponse {
  operation: MultipartSignOperation;
  method: "PUT" | "GET" | "POST" | "DELETE";
  presigned_url: string;
  expires_in: number;
  part_number?: number;
}

export interface UploadFile {
  id: string;
  name: string;
  type: string;
  size: number;
  data: File;
  progress: number;
  error?: string;
  uploadURL?: string;
  status: "waiting" | "uploading" | "success" | "error";
}

export interface UploadProgress {
  bytesUploaded: number;
  bytesTotal: number;
  percentage: number;
}
