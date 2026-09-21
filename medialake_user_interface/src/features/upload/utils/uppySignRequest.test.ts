import { describe, expect, it, vi } from "vitest";
import {
  MULTIPART_THRESHOLD_BYTES,
  contentTypeForSigning,
  createMethodOf,
  findFileForS3Key,
  getChunkSize,
  isCreateRequest,
  multipartOperationOf,
  stampS3Meta,
} from "./uppySignRequest";

const MB = 1024 * 1024;
const GB = 1024 * MB;

describe("isCreateRequest / createMethodOf", () => {
  it("treats a request without an uploadId as the create request", () => {
    expect(isCreateRequest({ method: "PUT", key: "k" })).toBe(true);
    expect(isCreateRequest({ method: "POST", key: "k" })).toBe(true);
    expect(isCreateRequest({ method: "POST", key: "k", uploadId: "u" })).toBe(false);
  });

  it("only accepts PUT or POST as create methods", () => {
    expect(createMethodOf({ method: "PUT", key: "k" })).toBe("PUT");
    expect(createMethodOf({ method: "POST", key: "k" })).toBe("POST");
    expect(() => createMethodOf({ method: "GET", key: "k" })).toThrow(/Unexpected create/);
  });
});

describe("multipartOperationOf", () => {
  it("maps the four multipart requests to the server's sign operations", () => {
    const base = { key: "k", uploadId: "u" } as const;
    expect(multipartOperationOf({ ...base, method: "PUT", partNumber: 3 })).toBe("part");
    expect(multipartOperationOf({ ...base, method: "GET" })).toBe("list");
    expect(multipartOperationOf({ ...base, method: "POST" })).toBe("complete");
    expect(multipartOperationOf({ ...base, method: "DELETE" })).toBe("abort");
  });
});

describe("contentTypeForSigning", () => {
  it("matches what the plugin sends in Content-Type", () => {
    // The signed header must equal the sent header or S3 rejects the signature.
    expect(contentTypeForSigning({ type: "video/mp4" })).toBe("video/mp4");
    expect(contentTypeForSigning({ type: "" })).toBe("application/octet-stream");
    expect(contentTypeForSigning({ type: null })).toBe("application/octet-stream");
    expect(contentTypeForSigning({})).toBe("application/octet-stream");
  });
});

describe("getChunkSize", () => {
  it("scales with file size and never drops below the S3 5 MiB minimum", () => {
    expect(getChunkSize({ size: 10 * MB })).toBe(5 * MB);
    expect(getChunkSize({ size: 500 * MB })).toBe(50 * MB);
    expect(getChunkSize({ size: 5 * GB })).toBe(100 * MB);
    expect(getChunkSize({ size: 50 * GB })).toBe(200 * MB);
    expect(getChunkSize({ size: 150 * GB })).toBe(500 * MB);
    expect(getChunkSize({ size: null })).toBe(5 * MB);
  });

  it("keeps a 500 GB file under S3's 10,000-part limit", () => {
    expect((500 * GB) / getChunkSize({ size: 500 * GB })).toBeLessThanOrEqual(10000);
  });

  it("agrees with the server on the multipart threshold", () => {
    expect(MULTIPART_THRESHOLD_BYTES).toBe(100 * MB);
  });
});

describe("findFileForS3Key / stampS3Meta", () => {
  const files = new Map<string, any>([
    ["file-1", { id: "file-1", meta: {} }],
    ["file-2", { id: "file-2", meta: { s3Key: "uploads/two.mp4" } }],
    [
      "file-3",
      { id: "file-3", meta: {}, s3Multipart: { uploadId: "u", key: "uploads/three.mov" } },
    ],
  ]);
  const uppy = {
    getFile: (id: string) => files.get(id),
    getFiles: () => [...files.values()],
    setFileMeta: vi.fn((id: string, meta: Record<string, unknown>) => {
      const f = files.get(id);
      f.meta = { ...f.meta, ...meta };
    }),
  } as any;

  it("resolves the create request by file id", () => {
    expect(findFileForS3Key(uppy, "file-1")?.id).toBe("file-1");
  });

  it("resolves later requests by the server key stamped on meta", () => {
    expect(findFileForS3Key(uppy, "uploads/two.mp4")?.id).toBe("file-2");
  });

  it("resolves a restored multipart upload by the persisted s3Multipart state", () => {
    // After a Golden Retriever restore only file state survives — no in-memory maps.
    expect(findFileForS3Key(uppy, "uploads/three.mov")?.id).toBe("file-3");
  });

  it("returns undefined for an unknown key", () => {
    expect(findFileForS3Key(uppy, "nope")).toBeUndefined();
  });

  it("stamps the server's decision onto the file meta", () => {
    stampS3Meta(uppy, "file-1", { key: "uploads/one.mp4", bucket: "b", connectorId: "c" });
    expect(uppy.setFileMeta).toHaveBeenCalledWith("file-1", {
      s3Key: "uploads/one.mp4",
      s3Bucket: "b",
      s3ConnectorId: "c",
    });
    expect(findFileForS3Key(uppy, "uploads/one.mp4")?.id).toBe("file-1");
  });

  it("omits the connector when there is none (portal uploads)", () => {
    stampS3Meta(uppy, "file-2", { key: "k", bucket: "b" });
    expect(uppy.setFileMeta).toHaveBeenLastCalledWith("file-2", { s3Key: "k", s3Bucket: "b" });
  });
});
