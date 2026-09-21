import React, { useEffect, useState, useRef, useCallback } from "react";
import Uppy from "@uppy/core";
import AwsS3 from "@uppy/aws-s3";
import GoldenRetriever from "@uppy/golden-retriever";
import Dashboard from "@uppy/react/dashboard";
import "@uppy/core/css/style.min.css";
import "@uppy/dashboard/css/style.min.css";
import { Alert, Box, Button } from "@mui/material";
import { useTranslation } from "react-i18next";
import { usePortalApi, PortalSessionExpiredError } from "../hooks/usePortalApi";
import type { PortalDestination, ConflictResolutionResult } from "../types/portal.types";
import {
  GOLDEN_RETRIEVER_EXPIRES_MS,
  MULTIPART_THRESHOLD_BYTES,
  contentTypeForSigning,
  createMethodOf,
  findFileForS3Key,
  getChunkSize,
  isCreateRequest,
  multipartOperationOf,
  stampS3Meta,
  type SignRequestInput,
  type SignRequestResult,
} from "@/features/upload/utils/uppySignRequest";
import { useServiceWorkerKeepalive } from "@/features/upload/hooks/useServiceWorkerKeepalive";
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

  // Per-file (filename, relative path) captured when the create request is signed so a
  // failed upload can be released against the session by rebuilding its key.
  const fileLocatorRef = useRef<Map<string, { filename: string; path: string }>>(new Map());
  const uppyRef = useRef<Uppy | null>(null);
  const portalApi = usePortalApi(portalSlug, sessionJwt, useCaptchaIntegration);
  // Keep the Golden Retriever service worker (and the blobs it holds) alive during long uploads.
  useServiceWorkerKeepalive(uppy);

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
    uppyRef.current = instance;

    // The browser performs every S3 request itself; the portal API only presigns. The
    // callback is bound once, so it reads the latest implementation through a ref.
    instance.use(AwsS3, {
      id: "PortalS3",
      limit: 6,
      getChunkSize,
      shouldUseMultipart: (file) => (file.size ?? 0) > MULTIPART_THRESHOLD_BYTES,
      // Placeholder key; the server returns the real one from the create request.
      generateObjectKey: (file) => file.id,
      signRequest: (request) => {
        const sign = signRequestRef.current;
        if (!sign) throw new Error("Uploader is not ready");
        return sign(request);
      },
    });

    // Recover the selection and in-flight multipart uploads after a refresh or crash.
    instance.use(GoldenRetriever, {
      serviceWorker: true,
      expires: GOLDEN_RETRIEVER_EXPIRES_MS,
    });

    setUppy(instance);

    return () => {
      uppyRef.current = null;
      instance.cancelAll();
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

  /**
   * Uppy 6's `signRequest` for the portal.
   *
   * The create request (PUT or CreateMultipartUpload POST; no uploadId) arrives with
   * `file.id` as its key, resolves the session, and asks the portal API to validate the
   * destination, record the batch directives and presign. The server's key is stamped onto
   * the file so every later request (part, list, complete, abort) can be matched back to it,
   * including after a Golden Retriever restore.
   *
   * Assigned on every render so it always sees the current path, destination and metadata.
   */
  const signRequestRef = useRef<
    ((request: SignRequestInput) => Promise<SignRequestResult>) | undefined
  >(undefined);
  signRequestRef.current = async (request) => {
    const instance = uppyRef.current;
    if (!instance) throw new Error("Uploader is not ready");

    if (isCreateRequest(request)) {
      const file = instance.getFile(request.key);
      if (!file) throw new Error(`Unknown file for upload key ${request.key}`);
      const safeCurrent = currentPath ?? "";
      const safeRoot = destination.rootPath ?? "";
      const relativePath =
        safeRoot && safeCurrent.startsWith(safeRoot)
          ? safeCurrent.slice(safeRoot.length)
          : safeCurrent;
      try {
        const sid = await ensureSession();
        const result = await portalApi.createUpload({
          filename: file.name ?? "",
          contentType: contentTypeForSigning(file),
          fileSize: file.size ?? 0,
          path: relativePath,
          destinationId: destination.destinationId,
          method: createMethodOf(request),
          metadata: metadataFields,
          sessionId: sid,
          batchToken: batchTokenRef.current,
        });
        fileCountRef.current += 1;
        fileLocatorRef.current.set(file.id, { filename: file.name ?? "", path: relativePath });
        stampS3Meta(instance, file.id, { key: result.key, bucket: result.bucket });
        return { url: result.url, key: result.key };
      } catch (e) {
        return catchSessionExpired(e);
      }
    }

    // Later multipart requests carry the server key; the destination is the one the
    // uploader is mounted for, so only the operation needs mapping.
    const operation = multipartOperationOf(request);
    if (!findFileForS3Key(instance, request.key)) {
      // Not fatal: the server validates the key against the destination root. Logged
      // because a miss here means a restored upload lost its file state.
      console.warn(`Portal upload key ${request.key} does not match a known file`);
    }
    try {
      const result = await portalApi.signMultipart({
        uploadId: request.uploadId as string,
        key: request.key,
        destinationId: destination.destinationId,
        operation,
        ...(operation === "part" ? { partNumber: request.partNumber } : {}),
      });
      return { url: result.presignedUrl };
    } catch (e) {
      return catchSessionExpired(e);
    }
  };

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
