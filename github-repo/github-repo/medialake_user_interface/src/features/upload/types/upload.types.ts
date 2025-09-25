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

export interface S3PresignedPostUrl {
  url: string;
  fields: Record<string, string>;
}

export interface S3UploadResponse {
  bucket: string;
  key: string;
  presigned_post?: {
    url: string;
    fields: Record<string, string>;
  };
  upload_id?: string;
  part_urls?: Array<{
    part_number: number;
    presigned_url: string;
  }>;
  expires_in: number;
  multipart: boolean;
  part_size?: number;
  total_parts?: number;
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

export interface UploadRequest {
  connector_id: string;
  filename: string;
  content_type: string;
  file_size: number;
  path?: string;
}

export interface UploadProgress {
  bytesUploaded: number;
  bytesTotal: number;
  percentage: number;
}
