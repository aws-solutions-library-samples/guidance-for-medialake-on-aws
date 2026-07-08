import React, { useEffect, useState, useRef, useCallback } from "react";
import Uppy from "@uppy/core";
import AwsS3 from "@uppy/aws-s3";
import Dashboard from "@uppy/react/dashboard";
import "@uppy/core/css/style.min.css";
import "@uppy/dashboard/css/style.min.css";
import { Alert, Box, Button } from "@mui/material";
import { useTranslation } from "react-i18next";
import { usePortalApi, PortalSessionExpiredError } from "../hooks/usePortalApi";
import type {
  PortalDestination,
  PortalMultipartMetadata,
  ConflictResolutionResult,
} from "../types/portal.types";
import UploadQueueTable from "./UploadQueueTable";
import ConflictResolutionDialog from "./ConflictResolutionDialog";
import type { UppyFile, Meta, Body } from "@uppy/core";

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
   * the localized "Upload assets" / "Uploading…" strings. The visual
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
  /** Called when the upload session id is resolved (created or resumed). */
  onSessionChange?: (sessionId: string) => void;
  /** Called with the count of successfully uploaded files as it changes. */
  onUploadedCountChange?: (count: number) => void;
  /** Called when an upload starts (true) or all uploads settle (false). */
  onUploadingChange?: (isUploading: boolean) => void;
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
  onSessionChange,
  onUploadedCountChange,
  onUploadingChange,
}) => {
  const [uppy, setUppy] = useState<Uppy | null>(null);
  const [files, setFiles] = useState<UppyFile<Meta, Body>[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadComplete, setUploadComplete] = useState(false);
  const [conflicts, setConflicts] = useState<string[]>([]);
  const [showConflicts, setShowConflicts] = useState(false);

  const multipartDataRef = useRef<Map<string, PortalMultipartMetadata>>(new Map());
  // Per-file (filename, relative path) captured at upload-parameter time so a
  // failed upload can be released against the session by rebuilding its key.
  const fileLocatorRef = useRef<Map<string, { filename: string; path: string }>>(new Map());
  const portalApi = usePortalApi(portalSlug, sessionJwt, useCaptchaIntegration);

  // Latest bridge callbacks held in refs so the Uppy event subscription does
  // not need to re-bind when the parent passes new closures.
  const onSessionChangeRef = useRef(onSessionChange);
  const onUploadedCountChangeRef = useRef(onUploadedCountChange);
  const onUploadingChangeRef = useRef(onUploadingChange);
  useEffect(() => {
    onSessionChangeRef.current = onSessionChange;
    onUploadedCountChangeRef.current = onUploadedCountChange;
    onUploadingChangeRef.current = onUploadingChange;
  });

  // --- Upload session state ---
  const sessionIdRef = useRef<string | null>(null);
  const fileCountRef = useRef<number>(0);
  const { t } = useTranslation();

  // Single-flight session creation. A multi-file batch fires several concurrent
  // getUploadParameters/createMultipartUpload calls (AwsS3 `limit`). Without a
  // shared promise, each call would read sessionIdRef.current === null before
  // any response returns and mint its own session — fragmenting the batch.
  // sessionPromiseRef memoizes the single in-flight create so every concurrent
  // caller awaits the SAME session.
  const sessionPromiseRef = useRef<Promise<string> | null>(null);
  // Stable per-mount batch token sent on every /upload request so the server
  // can dedupe a fragmented first wave onto one session (defense-in-depth).
  const batchTokenRef = useRef<string>(crypto.randomUUID());

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

  // Resolve the upload session, creating it at most once per mount. All
  // concurrent callers share a single in-flight startSession() promise so a
  // multi-file batch can never fragment into multiple sessions client-side.
  const ensureSession = useCallback(async (): Promise<string> => {
    // Honor a session already resolved (e.g. resumed on mount).
    if (sessionIdRef.current) return sessionIdRef.current;
    if (!sessionPromiseRef.current) {
      sessionPromiseRef.current = (async () => {
        const resp = await portalApi.startSession();
        sessionIdRef.current = resp.sessionId;
        sessionStorage.setItem(sessionStorageKey, resp.sessionId);
        onSessionChangeRef.current?.(resp.sessionId);
        return resp.sessionId;
      })();
      // On failure, clear the memoized promise so a later upload can retry.
      sessionPromiseRef.current.catch(() => {
        sessionPromiseRef.current = null;
      });
    }
    return sessionPromiseRef.current;
  }, [portalApi, sessionStorageKey]);

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
          onSessionChangeRef.current?.(storedId);
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

    const reportCount = () => {
      const count = uppy.getFiles().filter((f) => f.progress?.uploadComplete).length;
      onUploadedCountChangeRef.current?.(count);
    };
    const syncFiles = () => setFiles([...uppy.getFiles()]);
    const onUpload = () => {
      setIsUploading(true);
      setUploadComplete(false);
      onUploadingChangeRef.current?.(true);
    };
    const onUploadSuccess = () => {
      syncFiles();
      reportCount();
    };
    const onUploadError = (file?: UppyFile<Meta, Body>) => {
      // Release the failed key in real time so it stops inflating the
      // session's expectedCount (the completion-join denominator). Best-effort:
      // submit's count true-up and the server sweep are the backstops.
      const sid = sessionIdRef.current;
      const loc = file ? fileLocatorRef.current.get(file.id) : undefined;
      if (sid && loc) {
        portalApi
          .releaseKey(sid, {
            destinationId: destination.destinationId,
            filename: loc.filename,
            path: loc.path,
          })
          .catch(() => {
            // best-effort; submit true-up / sweep reconcile the count
          });
      }
      syncFiles();
    };
    const onComplete = () => {
      setIsUploading(false);
      setUploadComplete(true);
      onUploadingChangeRef.current?.(false);
      syncFiles();
      reportCount();
    };

    uppy.on("file-added", syncFiles);
    uppy.on("file-removed", syncFiles);
    uppy.on("upload-progress", syncFiles);
    uppy.on("upload-success", onUploadSuccess);
    uppy.on("upload-error", onUploadError);
    uppy.on("upload", onUpload);
    uppy.on("complete", onComplete);

    return () => {
      uppy.off("file-added", syncFiles);
      uppy.off("file-removed", syncFiles);
      uppy.off("upload-progress", syncFiles);
      uppy.off("upload-success", onUploadSuccess);
      uppy.off("upload-error", onUploadError);
      uppy.off("upload", onUpload);
      uppy.off("complete", onComplete);
    };
  }, [uppy, portalApi, destination.destinationId]);

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
          const sid = await ensureSession();
          const result = await portalApi.getPresignedUrl({
            filename: file.name,
            contentType: file.type,
            fileSize: file.size,
            path: relativePath,
            destinationId: destination.destinationId,
            metadata: metadataFields,
            sessionId: sid,
            batchToken: batchTokenRef.current,
          });
          if (!result.presignedPost) throw new Error("Missing presigned post data");
          fileCountRef.current += 1;
          fileLocatorRef.current.set(file.id, {
            filename: file.name,
            path: relativePath,
          });
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
          const sid = await ensureSession();
          const result = await portalApi.getPresignedUrl({
            filename: file.name,
            contentType: file.type,
            fileSize: file.size,
            path: relativePath,
            destinationId: destination.destinationId,
            metadata: metadataFields,
            sessionId: sid,
            batchToken: batchTokenRef.current,
          });
          if (!result.uploadId || !result.key || !result.bucket) {
            throw new Error("Missing multipart data");
          }
          fileCountRef.current += 1;
          fileLocatorRef.current.set(file.id, {
            filename: file.name,
            path: relativePath,
          });
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
    ensureSession,
  ]);

  // --- Heartbeat lives at the page level ---
  // The session heartbeat is driven by UploadPortalPage for the entire life of
  // the authenticated survey (any page, whether or not an upload is in flight),
  // so server-side "idle" means the browser is actually gone rather than
  // "uploads finished". Gating it here on `isUploading` would stop the moment
  // uploads completed, letting the idle timeout fire while the user is still
  // filling out the rest of the form.

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
          ? t("uploadPortals.public.uploading")
          : (submitButtonText && submitButtonText.trim()) || t("uploadPortals.public.uploadAssets")}
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
