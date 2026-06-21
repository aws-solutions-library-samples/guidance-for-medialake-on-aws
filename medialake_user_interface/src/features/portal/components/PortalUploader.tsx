import React, { useEffect, useState, useRef, useCallback } from "react";
import Uppy from "@uppy/core";
import AwsS3 from "@uppy/aws-s3";
import Dashboard from "@uppy/react/dashboard";
import "@uppy/core/css/style.min.css";
import "@uppy/dashboard/css/style.min.css";
import { Alert, Box, Button } from "@mui/material";
import { usePortalApi, PortalSessionExpiredError } from "../hooks/usePortalApi";
import type {
  PortalDestination,
  PortalMultipartMetadata,
  ConflictResolutionResult,
} from "../types/portal.types";
import UploadQueueTable from "./UploadQueueTable";
import ConflictResolutionDialog from "./ConflictResolutionDialog";
import type { UppyFile, Meta, Body } from "@uppy/core";
import { StorageHelper } from "@/common/helpers/storage-helper";

interface Props {
  portalSlug: string;
  sessionJwt: string;
  destination: PortalDestination;
  currentPath: string;
  metadataFields: Record<string, string>;
  maxFileSizeBytes?: number;
  maxFilesPerSession?: number;
  onSessionExpired: () => void;
  useCaptchaIntegration?: boolean;
  /**
   * Optional override for the primary upload button label. Defaults to
   * the legacy strings ("Upload Files" / "Uploading…"). The visual
   * editor's Content section exposes `appearance.content.submitButtonText`
   * which flows through this prop at render time (Requirement 12.12).
   */
  submitButtonText?: string;
  /** Message shown after a successful upload. */
  successMessage?: string;
  /** Text shown in the upload drop zone area. */
  dropZoneText?: string;
  /** Allowed file types for Uppy restrictions (MIME types or extensions). */
  allowedFileTypes?: string[];
  /** Visual style of the submit button. */
  buttonStyle?: "contained" | "outlined" | "text";
  /** Border-radius style of the submit button. */
  buttonRounding?: "square" | "rounded" | "pill";
}

const GB = 1024 * 1024 * 1024;
const MB = 1024 * 1024;

const PortalUploader: React.FC<Props> = ({
  portalSlug,
  sessionJwt,
  destination,
  currentPath,
  metadataFields,
  maxFileSizeBytes,
  maxFilesPerSession,
  onSessionExpired,
  useCaptchaIntegration,
  submitButtonText,
  successMessage,
  dropZoneText,
  allowedFileTypes,
  buttonStyle,
  buttonRounding,
}) => {
  const [uppy, setUppy] = useState<Uppy | null>(null);
  const [files, setFiles] = useState<UppyFile<Meta, Body>[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadComplete, setUploadComplete] = useState(false);
  const [conflicts, setConflicts] = useState<string[]>([]);
  const [showConflicts, setShowConflicts] = useState(false);

  const multipartDataRef = useRef<Map<string, PortalMultipartMetadata>>(new Map());
  const portalApi = usePortalApi(portalSlug, sessionJwt, useCaptchaIntegration);

  // --- Upload session state ---
  const sessionIdRef = useRef<string | null>(null);
  const fileCountRef = useRef<number>(0);
  const heartbeatIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const sessionStorageKey = `upload-session:${portalSlug}:${destination.destinationId}`;

  const catchSessionExpired = useCallback(
    (err: unknown) => {
      if (err instanceof PortalSessionExpiredError) {
        onSessionExpired();
      }
      throw err;
    },
    [onSessionExpired]
  );

  // --- Session resume on mount ---
  useEffect(() => {
    const storedId = sessionStorage.getItem(sessionStorageKey);
    if (!storedId) return;

    let cancelled = false;
    portalApi
      .getSession(storedId)
      .then((session) => {
        if (cancelled) return;
        if (session.status === "OPEN") {
          sessionIdRef.current = storedId;
        } else {
          sessionStorage.removeItem(sessionStorageKey);
        }
      })
      .catch(() => {
        if (!cancelled) {
          sessionStorage.removeItem(sessionStorageKey);
        }
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Initialize Uppy
  useEffect(() => {
    const instance = new Uppy({
      id: "portal-uploader",
      autoProceed: false,
      restrictions: {
        maxFileSize: maxFileSizeBytes ?? 500 * GB,
        maxNumberOfFiles: maxFilesPerSession ?? 500,
        ...(allowedFileTypes && allowedFileTypes.length > 0 ? { allowedFileTypes } : {}),
      },
    });

    instance.use(AwsS3, {
      id: "PortalS3",
      limit: 6,
      getChunkSize: (file: { size: number }) => {
        if (file.size >= 100 * GB) return 500 * MB;
        if (file.size >= 10 * GB) return 200 * MB;
        if (file.size >= 1 * GB) return 100 * MB;
        if (file.size >= 100 * MB) return 50 * MB;
        return 5 * MB;
      },
      retryDelays: [0, 1000, 3000, 5000, 10000],
      shouldUseMultipart: (file: { size: number }) => file.size > 100 * MB,
    } as any);

    setUppy(instance);

    return () => {
      instance.cancelAll();
      multipartDataRef.current.clear();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Sync files state from Uppy events
  useEffect(() => {
    if (!uppy) return;

    const syncFiles = () => setFiles([...uppy.getFiles()]);
    const onUpload = () => {
      setIsUploading(true);
      setUploadComplete(false);
    };
    const onComplete = () => {
      setIsUploading(false);
      setUploadComplete(true);
      syncFiles();
    };

    uppy.on("file-added", syncFiles);
    uppy.on("file-removed", syncFiles);
    uppy.on("upload-progress", syncFiles);
    uppy.on("upload-success", syncFiles);
    uppy.on("upload-error", syncFiles);
    uppy.on("upload", onUpload);
    uppy.on("complete", onComplete);

    return () => {
      uppy.off("file-added", syncFiles);
      uppy.off("file-removed", syncFiles);
      uppy.off("upload-progress", syncFiles);
      uppy.off("upload-success", syncFiles);
      uppy.off("upload-error", syncFiles);
      uppy.off("upload", onUpload);
      uppy.off("complete", onComplete);
    };
  }, [uppy]);

  // Configure S3 plugin callbacks when dependencies change
  useEffect(() => {
    if (!uppy) return;

    const awsS3 = uppy.getPlugin("PortalS3") as any;
    if (!awsS3) return;

    awsS3.setOptions({
      getUploadParameters: async (file: any) => {
        const safeCurrent = currentPath ?? "";
        const safeRoot = destination.rootPath ?? "";
        const relativePath =
          safeRoot && safeCurrent.startsWith(safeRoot)
            ? safeCurrent.slice(safeRoot.length)
            : safeCurrent;
        try {
          const result = await portalApi.getPresignedUrl({
            filename: file.name,
            contentType: file.type,
            fileSize: file.size,
            path: relativePath,
            destinationId: destination.destinationId,
            metadata: metadataFields,
            sessionId: sessionIdRef.current || undefined,
          });
          if (!result.presignedPost) throw new Error("Missing presigned post data");
          // Lazily capture sessionId from the response
          if (result.sessionId && !sessionIdRef.current) {
            sessionIdRef.current = result.sessionId;
            sessionStorage.setItem(sessionStorageKey, result.sessionId);
          }
          fileCountRef.current += 1;
          return {
            method: "POST" as const,
            url: result.presignedPost.url,
            fields: result.presignedPost.fields,
          };
        } catch (e) {
          return catchSessionExpired(e);
        }
      },

      createMultipartUpload: async (file: any) => {
        const safeCurrent = currentPath ?? "";
        const safeRoot = destination.rootPath ?? "";
        const relativePath =
          safeRoot && safeCurrent.startsWith(safeRoot)
            ? safeCurrent.slice(safeRoot.length)
            : safeCurrent;
        try {
          const result = await portalApi.getPresignedUrl({
            filename: file.name,
            contentType: file.type,
            fileSize: file.size,
            path: relativePath,
            destinationId: destination.destinationId,
            metadata: metadataFields,
            sessionId: sessionIdRef.current || undefined,
          });
          if (!result.uploadId || !result.key || !result.bucket) {
            throw new Error("Missing multipart data");
          }
          // Lazily capture sessionId from the response
          if (result.sessionId && !sessionIdRef.current) {
            sessionIdRef.current = result.sessionId;
            sessionStorage.setItem(sessionStorageKey, result.sessionId);
          }
          fileCountRef.current += 1;
          multipartDataRef.current.set(file.id, {
            uploadId: result.uploadId,
            key: result.key,
            bucket: result.bucket,
          });
          return { uploadId: result.uploadId, key: result.key };
        } catch (e) {
          return catchSessionExpired(e);
        }
      },

      signPart: async (file: any, partData: any) => {
        const data = multipartDataRef.current.get(file.id);
        if (!data) throw new Error("Multipart data not found");
        try {
          const result = await portalApi.signPart({
            uploadId: data.uploadId,
            key: data.key,
            partNumber: partData.partNumber,
            destinationId: destination.destinationId,
          });
          return { url: result.presignedUrl };
        } catch (e) {
          return catchSessionExpired(e);
        }
      },

      completeMultipartUpload: async (file: any, data: any) => {
        const mp = multipartDataRef.current.get(file.id);
        if (!mp) throw new Error("Multipart data not found");
        try {
          const result = await portalApi.completeMultipart({
            uploadId: mp.uploadId,
            key: mp.key,
            parts: data.parts,
            destinationId: destination.destinationId,
          });
          multipartDataRef.current.delete(file.id);
          return { location: result.location };
        } catch (e) {
          multipartDataRef.current.delete(file.id);
          return catchSessionExpired(e);
        }
      },

      abortMultipartUpload: async (file: any) => {
        const mp = multipartDataRef.current.get(file.id);
        if (mp) {
          try {
            await portalApi.abortMultipart({
              uploadId: mp.uploadId,
              key: mp.key,
              destinationId: destination.destinationId,
            });
          } catch {
            // best-effort
          }
          multipartDataRef.current.delete(file.id);
        }
      },
    });
  }, [
    uppy,
    portalApi,
    currentPath,
    destination.destinationId,
    destination.rootPath,
    metadataFields,
    catchSessionExpired,
    sessionStorageKey,
  ]);

  // --- Heartbeat: post every ~30s while uploading and a sessionId exists ---
  useEffect(() => {
    if (!isUploading || !sessionIdRef.current) {
      if (heartbeatIntervalRef.current) {
        clearInterval(heartbeatIntervalRef.current);
        heartbeatIntervalRef.current = null;
      }
      return;
    }

    heartbeatIntervalRef.current = setInterval(() => {
      const sid = sessionIdRef.current;
      if (sid) {
        portalApi.heartbeat(sid).catch(() => {
          // best-effort; a failed heartbeat should not crash the uploader
        });
      }
    }, 30_000);

    return () => {
      if (heartbeatIntervalRef.current) {
        clearInterval(heartbeatIntervalRef.current);
        heartbeatIntervalRef.current = null;
      }
    };
  }, [isUploading, portalApi]);

  // --- Finalize on Uppy `complete` event ---
  useEffect(() => {
    if (!uppy) return;

    const onUploadComplete = () => {
      const sid = sessionIdRef.current;
      if (!sid) return;
      portalApi.finalize(sid, fileCountRef.current).catch(() => {
        // best-effort; finalize is idempotent and the sweep is the safety net
      });
    };

    uppy.on("complete", onUploadComplete);
    return () => {
      uppy.off("complete", onUploadComplete);
    };
  }, [uppy, portalApi]);

  // --- Finalize on beforeunload via fetch keepalive ---
  useEffect(() => {
    const handleBeforeUnload = () => {
      const sid = sessionIdRef.current;
      if (!sid) return;

      const baseURL = StorageHelper.getAwsConfig()?.API?.REST?.RestApi?.endpoint || "";
      const url = `${baseURL}/portal/${portalSlug}/upload-session/${sid}/finalize`;

      try {
        fetch(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Portal-Session": sessionJwt,
          },
          body: JSON.stringify({ fileCount: fileCountRef.current }),
          keepalive: true,
        });
      } catch {
        // best-effort; cannot handle errors during unload
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [portalSlug, sessionJwt]);

  // --- Cleanup heartbeat on unmount ---
  useEffect(() => {
    return () => {
      if (heartbeatIntervalRef.current) {
        clearInterval(heartbeatIntervalRef.current);
        heartbeatIntervalRef.current = null;
      }
    };
  }, []);

  const handleUpload = async () => {
    if (!uppy || files.length === 0) return;

    // Conflict detection
    try {
      const listing = await portalApi.browse(currentPath, destination.destinationId);
      const existingNames = new Set(
        (listing.objects || []).map((o: any) => o.key?.split("/").pop())
      );
      const conflicting = files.filter((f) => existingNames.has(f.name)).map((f) => f.name);

      if (conflicting.length > 0) {
        setConflicts(conflicting);
        setShowConflicts(true);
        return;
      }
    } catch (e) {
      if (e instanceof PortalSessionExpiredError) {
        onSessionExpired();
        return;
      }
      // If browse fails, proceed with upload anyway
    }

    uppy.upload();
  };

  const handleConflictResolve = ({ action, applyToAll }: ConflictResolutionResult) => {
    setShowConflicts(false);
    if (!uppy) return;

    if (action === "skip") {
      if (applyToAll) {
        // Skip-all — drop every conflicting file, upload the rest.
        const conflictSet = new Set(conflicts);
        uppy.getFiles().forEach((f) => {
          if (conflictSet.has(f.name)) uppy.removeFile(f.id);
        });
        setConflicts([]);
        if (uppy.getFiles().length > 0) {
          uppy.upload();
        }
      } else {
        // Skip-one — remove only the first conflicting file, then if
        // any conflicts remain re-prompt the user instead of silently
        // overwriting the others.
        const first = uppy.getFiles().find((f) => conflicts.includes(f.name));
        if (first) {
          uppy.removeFile(first.id);
          setConflicts((prev) => prev.filter((name) => name !== first.name));
        }
        const remaining = conflicts.filter((name) => name !== first?.name);
        if (remaining.length > 0) {
          setShowConflicts(true);
          return;
        }
        if (uppy.getFiles().length > 0) {
          uppy.upload();
        }
      }
      return;
    }

    // Overwrite (apply-to-all or single — we overwrite regardless since
    // the user explicitly opted in). Clear the conflicts list and kick
    // off the upload.
    setConflicts([]);
    if (uppy.getFiles().length > 0) {
      uppy.upload();
    }
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
      {uppy && (
        <Dashboard
          uppy={uppy}
          width="100%"
          height={200}
          hideUploadButton
          proudlyDisplayPoweredByUppy={false}
          note={dropZoneText || undefined}
        />
      )}

      {uppy && (
        <UploadQueueTable
          files={files}
          onRemoveFile={(id) => uppy.removeFile(id)}
          onClearAll={() => uppy.cancelAll()}
        />
      )}

      {uploadComplete && (
        <Alert severity="success" onClose={() => setUploadComplete(false)}>
          {successMessage || "Upload complete!"}
        </Alert>
      )}

      <Button
        variant={buttonStyle || "contained"}
        onClick={handleUpload}
        disabled={files.length === 0 || isUploading}
        fullWidth
        sx={{
          borderRadius:
            buttonRounding === "square" ? 0 : buttonRounding === "pill" ? "9999px" : undefined,
        }}
      >
        {isUploading
          ? "Uploading…"
          : (submitButtonText && submitButtonText.trim()) || "Upload Files"}
      </Button>

      <ConflictResolutionDialog
        open={showConflicts}
        conflictingFilenames={conflicts}
        onResolve={handleConflictResolve}
        onClose={() => setShowConflicts(false)}
      />
    </Box>
  );
};

export default PortalUploader;
