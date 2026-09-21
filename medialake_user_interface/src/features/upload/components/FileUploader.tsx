import React, { useEffect, useState, useRef, useMemo, useCallback } from "react";
import Uppy from "@uppy/core";
import Dashboard from "@uppy/react/dashboard";
import AwsS3 from "@uppy/aws-s3";
import GoldenRetriever from "@uppy/golden-retriever";
import "@uppy/core/css/style.min.css";
import "@uppy/dashboard/css/style.min.css";
import {
  Box,
  Button,
  Chip,
  FormControl,
  IconButton,
  InputLabel,
  ListSubheader,
  MenuItem,
  Paper,
  Select,
  SelectChangeEvent,
  Tooltip,
  Typography,
  Alert,
} from "@mui/material";
import FolderIcon from "@mui/icons-material/Folder";
import PersonIcon from "@mui/icons-material/Person";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import StarIcon from "@mui/icons-material/Star";
import StarBorderIcon from "@mui/icons-material/StarBorder";
import { useTranslation } from "react-i18next";
import { useSearchConnectors } from "@/api/hooks/useSearchConnectors";
import { useGetAllCollections } from "@/api/hooks/useCollections";
import { usePermission } from "@/permissions";
import useS3Upload from "../hooks/useS3Upload";
import { useServiceWorkerKeepalive } from "../hooks/useServiceWorkerKeepalive";
import {
  GOLDEN_RETRIEVER_EXPIRES_MS,
  MULTIPART_THRESHOLD_BYTES,
  S3_META_CONNECTOR_ID,
  contentTypeForSigning,
  createMethodOf,
  findFileForS3Key,
  getChunkSize,
  isCreateRequest,
  multipartOperationOf,
  stampS3Meta,
  type SignRequestInput,
  type SignRequestResult,
} from "../utils/uppySignRequest";
import PathBrowser from "./PathBrowser";
import CollectionSelector, { CollectionRef } from "./CollectionSelector";
import { useUploadLocations } from "../hooks/useUploadLocations";
import { normalizeUploadPath, type UploadLocation } from "../types/uploadLocation.types";
import { typography } from "@/theme/tokens";

// Define meta type to make typings clearer
type Meta = Record<string, any>;

// This ensures the imports only happen in the browser, not during build
// We're using function declarations to avoid TypeScript errors with dynamic imports
function getUppy() {
  return new Uppy({
    id: "uppy-s3-uploader",
    autoProceed: false,
    debug: process.env.NODE_ENV === "development",
    restrictions: {
      maxFileSize: 500 * 1024 * 1024 * 1024, // 500GB max file size
      allowedFileTypes: [
        "audio/*",
        "video/*",
        "image/*",
        "application/x-mpegURL", // HLS
        "application/dash+xml", // MPEG-DASH
        "application/mxf", // MXF
      ],
      maxNumberOfFiles: 500,
    },
  });
}

// S3-compatible filename regex.
// Allows: alphanumeric, S3 safe chars (!-_.*'()), and chars that require
// URL-encoding but are fully supported (space @$+,;=&:).
// Blocks: control chars and S3 "characters to avoid" (\{}^`~|%<>"#[])
const FILENAME_REGEX = /^[a-zA-Z0-9!\-_.*'() @$+,;=&:]+$/;

/**
 * FileUploaderProps interface
 * @param path - Initial upload path; component manages its own path state internally
 * @param onPathChange - Optional callback called when user selects a new path
 */
interface FileUploaderProps {
  onUploadComplete?: (files: any[]) => void;
  onUploadError?: (error: Error, file: any) => void;
  path?: string;
  onPathChange?: (path: string) => void;
  defaultConnectorId?: string;
  lockConnector?: boolean;
  defaultObjectPrefix?: string;
}

const FileUploader: React.FC<FileUploaderProps> = ({
  onUploadComplete,
  onUploadError,
  path = "",
  onPathChange,
  defaultConnectorId,
  lockConnector,
  defaultObjectPrefix,
}) => {
  const { t } = useTranslation();
  const { can } = usePermission();
  // Shared (non-My-Assets) connectors are only offered as upload destinations
  // to users who can upload into connectors. My Assets is always exempt.
  const canUploadToConnectors = can("upload", "connector");
  // Browsing paths calls GET /connectors/s3/explorer/{id}, which requires connectors:view.
  // Without it the request 403s and the global interceptor would bounce the user to
  // /access-denied, so hide the browse affordance instead and leave them on the default path.
  const canBrowsePaths = can("view", "connector");
  const [uppy, setUppy] = useState<Uppy<Meta> | null>(null);
  const [selectedConnector, setSelectedConnector] = useState<string>("");
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadPath, setUploadPath] = useState<string>(path || "");
  const [isPathBrowserOpen, setIsPathBrowserOpen] = useState<boolean>(false);
  const [selectedCollections, setSelectedCollections] = useState<CollectionRef[]>([]);
  const { data: connectorsResponse, isLoading: isLoadingConnectors } = useSearchConnectors();
  const { createUpload, signMultipart } = useS3Upload();
  // Keep the Golden Retriever service worker (and the blobs it holds) alive during long uploads.
  useServiceWorkerKeepalive(uppy);

  // Filter only S3 connectors that are active and have uploads enabled
  const connectors =
    connectorsResponse?.data?.connectors.filter(
      (connector) =>
        connector.type === "s3" &&
        connector.status === "active" &&
        connector.configuration?.allowUploads !== false
    ) || [];

  // Memoize collection ids for the upload request body and Uppy meta
  // (defined after the saved-locations hook, which supplies the reconciler)

  // Connectors the user can pick from, excluding the My Assets virtual connector.
  // When the connector is locked (e.g. "Upload to My Assets"), or the user
  // lacks the connectors:upload permission, no other connectors are selectable
  // — only My Assets remains available.
  const otherConnectors = connectors.filter((c) => c.id !== defaultConnectorId);
  const selectableConnectors = lockConnector || !canUploadToConnectors ? [] : otherConnectors;

  // My Assets is a valid destination only when a defaultConnectorId is provided.
  const hasMyAssets = !!defaultConnectorId;

  // The single connector destination (when My Assets is not present).
  const singleConnector = !hasMyAssets ? selectableConnectors[0] : undefined;

  // When there is exactly one selectable connector and no My Assets, that
  // connector is auto-selected (no dropdown is shown).
  const autoSelectConnectorId =
    !hasMyAssets && selectableConnectors.length === 1 ? selectableConnectors[0].id : undefined;

  // ── Saved upload locations ────────────────────────────────────────────────
  // Live collections, used to drop saved collections that no longer resolve.
  // CollectionSelector already issues this query, so this shares its cache.
  const { data: allCollectionsData } = useGetAllCollections();
  const liveCollections = allCollectionsData?.data;

  const {
    isLoading: isLoadingSavedLocations,
    availableFavorites,
    isSaved,
    isAtCapacity,
    maxFavorites,
    toggleSaved,
    rememberLastLocation,
    restorableLastLocation,
    reconcileCollections,
  } = useUploadLocations({
    selectableConnectors,
    myAssetsConnectorId: defaultConnectorId,
    myAssetsObjectPrefix: defaultObjectPrefix,
    liveCollections,
  });

  // Surfaced when a saved location referenced collections that no longer resolve.
  const [droppedCollectionNotice, setDroppedCollectionNotice] = useState<string>("");

  /**
   * Validate the selected collections on every upload.
   *
   * `POST /assets/upload` caps the number of collections but never checks that they exist —
   * it just stamps the ids into S3 user-metadata for a downstream step to consume. A
   * collection can be deleted, or the user can lose edit rights on it, while the uploader
   * is open or between saving a location and using it. Reconciling here means the request
   * only ever carries ids that currently exist and are still addable.
   *
   * The stale entries are deliberately left visible in the picker rather than silently
   * deselected: a transient collections-query failure should not destroy the user's
   * selection. The warning explains what will not be applied.
   */
  const { collections: validatedCollections, dropped: droppedSelectedCollections } = useMemo(
    () =>
      reconcileCollections(
        selectedCollections.map((collection) => ({ id: collection.id, name: collection.name }))
      ),
    [reconcileCollections, selectedCollections]
  );

  // Memoized collection ids for the upload request body and Uppy meta
  const collectionIds = useMemo(
    () => validatedCollections.map((collection) => collection.id),
    [validatedCollections]
  );

  const collectionWarnings = useMemo(() => {
    const messages: string[] = [];
    if (droppedCollectionNotice) messages.push(droppedCollectionNotice);
    if (droppedSelectedCollections.length > 0) {
      messages.push(
        t("upload.savedLocations.selectedCollectionsUnavailable", {
          count: droppedSelectedCollections.length,
          names: droppedSelectedCollections.map((collection) => collection.name).join(", "),
          defaultValue_one:
            "A selected collection is no longer available and will not be applied: {{names}}",
          defaultValue_other:
            "{{count}} selected collections are no longer available and will not be applied: {{names}}",
        })
      );
    }
    return messages;
  }, [droppedCollectionNotice, droppedSelectedCollections, t]);

  /**
   * Selectable destinations. A destination is (connector, path), so favorites are listed
   * as first-class options alongside connectors — two favorites on the same connector
   * with different paths are two distinct destinations, which a connector-keyed dropdown
   * could not express.
   */
  const favoriteOptions = useMemo(
    () =>
      availableFavorites.map((favorite) => ({
        key: `fav:${favorite.id}`,
        label: favorite.label,
        connectorId: favorite.connectorId,
        path: favorite.path,
        collections: favorite.collections,
      })),
    [availableFavorites]
  );

  const connectorOptions = useMemo(() => {
    const options: Array<{
      key: string;
      label: string;
      connectorId: string;
      isMyAssets: boolean;
    }> = [];

    if (hasMyAssets && defaultConnectorId) {
      options.push({
        key: `conn:${defaultConnectorId}`,
        label: "My Assets",
        connectorId: defaultConnectorId,
        isMyAssets: true,
      });
    }
    for (const connector of selectableConnectors) {
      options.push({
        key: `conn:${connector.id}`,
        label: `${connector.name} (${connector.storageIdentifier})`,
        connectorId: connector.id,
        isMyAssets: false,
      });
    }
    return options;
  }, [hasMyAssets, defaultConnectorId, selectableConnectors]);

  // Total destinations available to the user. If the user can't read any
  // connectors (e.g. no permission) and has no personal My Assets space,
  // this is 0 and uploads are blocked.
  const destinationCount = favoriteOptions.length + connectorOptions.length;
  const hasNoDestinations = destinationCount === 0;
  const hasSingleDestination = destinationCount === 1;

  // Sync uploadPath with path prop
  useEffect(() => {
    setUploadPath(path || "");
  }, [path]);

  /**
   * Apply a destination: connector, path and (for saved locations) target collections,
   * all in one go. Doing it atomically matters — `handleConnectorChange` clears the path,
   * so setting the two separately would lose a saved location's path.
   */
  const applyUploadLocation = useCallback(
    (location: UploadLocation) => {
      setSelectedConnector(location.connectorId);

      const nextPath = normalizeUploadPath(location.path);
      setUploadPath(nextPath);
      if (onPathChange) {
        onPathChange(nextPath);
      }

      // `POST /assets/upload` does not verify that collection ids still exist, so a saved
      // location could otherwise silently carry dead references. Reconcile against the
      // live list and tell the user what was dropped.
      const { collections, dropped } = reconcileCollections(location.collections);
      setSelectedCollections(collections);
      setDroppedCollectionNotice(
        dropped.length > 0
          ? t("upload.savedLocations.collectionsUnavailable", {
              count: dropped.length,
              names: dropped.map((collection) => collection.name).join(", "),
              defaultValue_one:
                "A collection saved with this location is no longer available and was removed: {{names}}",
              defaultValue_other:
                "{{count}} collections saved with this location are no longer available and were removed: {{names}}",
            })
          : ""
      );
    },
    [onPathChange, reconcileCollections, t]
  );

  // Pre-select the destination automatically, in two layers.
  //
  // Layer 1 (unchanged from before this feature) selects My Assets as soon as a
  // defaultConnectorId is available, or the sole connector. It deliberately still re-fires
  // when defaultConnectorId changes, because TopBar passes it as undefined until
  // useMyAssetsConnector resolves. Keeping it ungated means the uploader is usable
  // immediately and never waits on an optional preference request.
  //
  // Layer 2 then refines the choice to the last location this user uploaded to, once the
  // saved settings and the connector list have both arrived. It yields to layer 1 for the
  // initial paint and bows out entirely if the user has already touched the destination —
  // saved locations load asynchronously, so without that guard a slow response could yank
  // the destination out from under someone who had already picked one.
  const hasRestoredLastLocationRef = useRef(false);
  const userTouchedDestinationRef = useRef(false);
  const isResolvingSavedLocation = isLoadingConnectors || isLoadingSavedLocations;

  useEffect(() => {
    if (hasRestoredLastLocationRef.current) return;
    if (defaultConnectorId) {
      setSelectedConnector(defaultConnectorId);
    } else if (autoSelectConnectorId) {
      setSelectedConnector(autoSelectConnectorId);
    }
  }, [defaultConnectorId, autoSelectConnectorId]);

  useEffect(() => {
    if (hasRestoredLastLocationRef.current) return;
    if (userTouchedDestinationRef.current) return;
    if (isResolvingSavedLocation) return;

    // A caller-pinned destination always wins: an explicit path prop or a locked connector
    // means the caller chose deliberately (e.g. "Upload to My Assets", or a
    // connector-scoped upload), so a remembered location must not override it.
    if (lockConnector || path) return;

    if (!restorableLastLocation) return;

    hasRestoredLastLocationRef.current = true;
    applyUploadLocation(restorableLastLocation);
  }, [isResolvingSavedLocation, lockConnector, path, restorableLastLocation, applyUploadLocation]);

  // Helper function to parse objectPrefix into array
  const parseObjectPrefix = (objectPrefix: string | string[] | undefined): string[] => {
    if (!objectPrefix) return [];
    if (typeof objectPrefix === "string") {
      const trimmed = objectPrefix.trim();
      return trimmed ? [trimmed] : [];
    }
    return objectPrefix.map((prefix) => prefix.trim()).filter((prefix) => prefix !== "");
  };

  // Get the selected connector object
  const selectedConnectorObj = useMemo(
    () => connectors.find((c) => c.id === selectedConnector),
    [connectors, selectedConnector]
  );

  // Determine if My Assets is currently selected
  const isMyAssetsSelected = !!defaultConnectorId && selectedConnector === defaultConnectorId;

  // Extract and parse allowedPrefixes from selected connector
  // Fallback to configuration.objectPrefix if top-level objectPrefix is undefined
  //
  // My Assets is not in the connectors list (FileUploader filters it out to render it
  // separately), so its prefix comes from the caller-provided defaultObjectPrefix — the
  // user's own `personal/{sub}/`. It is treated as an allowed prefix rather than a hardcoded
  // value so the generic defaulting below fills it in, but the personal bucket and path are
  // never surfaced to the user: they are shared-infrastructure details.
  const allowedPrefixes = useMemo(() => {
    if (isMyAssetsSelected) {
      return parseObjectPrefix(defaultObjectPrefix);
    }
    const topLevelPrefix = selectedConnectorObj?.objectPrefix;
    const configPrefix = selectedConnectorObj?.configuration?.objectPrefix;
    const prefixToUse = topLevelPrefix !== undefined ? topLevelPrefix : configPrefix;
    return parseObjectPrefix(prefixToUse);
  }, [selectedConnectorObj, isMyAssetsSelected, defaultObjectPrefix]);

  /**
   * The destination as it is saved and remembered.
   *
   * For My Assets the path is deliberately empty rather than the resolved
   * `personal/{sub}/`. The personal bucket is shared infrastructure and that prefix is an
   * internal detail, so it must never be persisted into a user-visible saved location or
   * rendered in a label. An empty path means "the connector's default root", which the
   * prefix-defaulting effect resolves back to `personal/{sub}/` when the location is applied.
   *
   * It also keeps identity consistent: My Assets is one destination with no path dimension,
   * which is accurate now that browsing inside it is not offered.
   *
   * For every other connector the *resolved* path is stored, not the raw `uploadPath`. A
   * connector with allowed prefixes has its empty path replaced by `allowedPrefixes[0]` by
   * the defaulting effect, so storing "" would leave the entry permanently unmatched: the
   * user would pick it and immediately see the dropdown fall back to the plain connector
   * entry with the star showing "not saved".
   *
   * Declared here, above the Uppy effects, because those depend on it.
   */
  const persistablePath = isMyAssetsSelected
    ? ""
    : normalizeUploadPath(uploadPath || allowedPrefixes[0]);

  // Default the path to the first allowed prefix when the connector restricts them and no
  // path is set yet. This covers My Assets too, whose only allowed prefix is the user's
  // personal folder — so it lands on `personal/{sub}/` by default but no longer forces the
  // path back there on every render, which would have discarded a chosen sub-path.
  useEffect(() => {
    if (selectedConnector && allowedPrefixes.length > 0 && (!uploadPath || uploadPath === "/")) {
      const firstPrefix = allowedPrefixes[0];
      const normalizedPrefix = firstPrefix.endsWith("/") ? firstPrefix : `${firstPrefix}/`;
      setUploadPath(normalizedPrefix);
      if (onPathChange) {
        onPathChange(normalizedPrefix);
      }
    }
  }, [selectedConnector, allowedPrefixes, uploadPath, onPathChange]);

  const uppyRef = useRef<Uppy<Meta> | null>(null);

  // The destination Uppy should sign against. Kept in a ref because signRequest is bound
  // once, when the plugin is installed, but the user can change connector, path and
  // collections until the upload starts.
  const destinationRef = useRef({
    connectorId: "",
    path: "",
    collectionIds: [] as string[],
  });
  destinationRef.current = {
    connectorId: selectedConnector,
    path: uploadPath,
    collectionIds,
  };

  /**
   * Uppy 6's `signRequest`: one presigned URL per S3 request the browser is about to make.
   *
   * The create request (PUT for a single-part object, POST for CreateMultipartUpload)
   * arrives with `file.id` as its key — see `generateObjectKey` — and goes to
   * `POST /assets/upload`, which validates the destination, records the collection
   * directives and returns the key it chose. That key is stamped onto the file so every
   * later request (part, list, complete, abort; all carry the server key and an uploadId)
   * can be routed to the same connector, including after a Golden Retriever restore.
   */
  const signRequestRef = useRef<
    ((request: SignRequestInput) => Promise<SignRequestResult>) | undefined
  >(undefined);
  signRequestRef.current = async (request) => {
    const instance = uppyRef.current;
    if (!instance) {
      throw new Error("Uploader is not ready");
    }

    if (isCreateRequest(request)) {
      const file = instance.getFile(request.key);
      if (!file) {
        throw new Error(`Unknown file for upload key ${request.key}`);
      }
      const { connectorId, path, collectionIds: collections } = destinationRef.current;
      if (!connectorId) {
        throw new Error("Select a destination before uploading");
      }
      const result = await createUpload({
        connector_id: connectorId,
        filename: file.name ?? "",
        content_type: contentTypeForSigning(file),
        file_size: file.size ?? 0,
        path,
        collection_ids: collections,
        method: createMethodOf(request),
      });
      stampS3Meta(instance, file.id, {
        key: result.key,
        bucket: result.bucket,
        connectorId,
      });
      return { url: result.url, key: result.key };
    }

    const file = findFileForS3Key(instance, request.key);
    const connectorId =
      (file?.meta as Record<string, unknown> | undefined)?.[S3_META_CONNECTOR_ID] ??
      destinationRef.current.connectorId;
    if (typeof connectorId !== "string" || !connectorId) {
      throw new Error(`No connector recorded for upload key ${request.key}`);
    }
    const operation = multipartOperationOf(request);
    const result = await signMultipart({
      connector_id: connectorId,
      upload_id: request.uploadId as string,
      key: request.key,
      operation,
      ...(operation === "part" ? { part_number: request.partNumber } : {}),
    });
    return { url: result.presigned_url };
  };

  // Initialize Uppy when the component mounts
  useEffect(() => {
    if (typeof window === "undefined") return;

    // Create Uppy instance
    const uppyInstance = getUppy();
    uppyRef.current = uppyInstance;

    // Validate filenames
    uppyInstance.on("file-added", (file) => {
      if (!FILENAME_REGEX.test(file.name ?? "")) {
        uppyInstance.info(
          `Filename "${file.name}" contains characters not supported by S3. Avoid: \\ { } ^ \` ~ | % < > " # [ ]`, // i18n-ignore
          "error",
          5000
        );
        uppyInstance.removeFile(file.id);
      }
    });

    // The browser performs every S3 request itself; the server only presigns.
    uppyInstance.use(AwsS3, {
      id: "S3Uploader",
      // Concurrent requests — conservative since S3 uses HTTP/1.1 and each multipart
      // file generates many sign requests.
      limit: 6,
      shouldUseMultipart: (file) => (file.size ?? 0) > MULTIPART_THRESHOLD_BYTES,
      getChunkSize,
      // The placeholder the create request carries; the server replaces it with the real
      // key, which signRequest reads back from the response.
      generateObjectKey: (file) => file.id,
      signRequest: (request) => {
        const sign = signRequestRef.current;
        if (!sign) throw new Error("Uploader is not ready");
        return sign(request);
      },
    });

    // Recover the selection and in-flight multipart uploads after a crash, a closed tab or
    // an accidental refresh. State and small files live in IndexedDB; the service worker
    // (registered at app start, see main.tsx) keeps references to larger files.
    uppyInstance.use(GoldenRetriever, {
      serviceWorker: true,
      expires: GOLDEN_RETRIEVER_EXPIRES_MS,
    });

    setUppy(uppyInstance);

    // Clean up function
    return () => {
      uppyRef.current = null;
      try {
        // Cancel any ongoing uploads and remove all files
        uppyInstance.cancelAll();
      } catch (e) {
        console.error("Error cleaning up Uppy instance:", e);
      }
    };
  }, []);

  // Set up event handlers
  useEffect(() => {
    if (!uppy) return;

    const handleUpload = () => {
      setIsUploading(true);
    };

    const handleUploadSuccess = (file: any, response: any) => {};

    const handleUploadError = (file: any, error: Error) => {
      const isMultipart = file.size > 100 * 1024 * 1024;
      console.error("Upload error:", {
        fileName: file.name,
        fileSize: file.size,
        connectorId: selectedConnector,
        isMultipart,
        error: error.message,
      });
      if (onUploadError) {
        onUploadError(error, file);
      }
    };

    const handleComplete = (result: { successful: any[] }) => {
      setIsUploading(false);
      if (selectedCollections.length > 0 && result.successful?.length > 0) {
        uppy.info(
          "Files will be added to the selected collections after processing completes.",
          "info",
          5000
        );
      }
      // Remember where this actually went so the next uploader open restores it.
      // Written on completion rather than per file, so one upload session is one write.
      // persistablePath, not uploadPath — see its definition for why My Assets stores no path.
      if (result.successful?.length > 0 && selectedConnector) {
        rememberLastLocation({
          connectorId: selectedConnector,
          path: persistablePath,
          collections: validatedCollections,
        });
      }
      if (onUploadComplete) {
        onUploadComplete(result.successful);
      }
    };

    const handleCancelAll = () => {
      setIsUploading(false);
    };

    uppy.on("upload", handleUpload);
    uppy.on("upload-success", handleUploadSuccess);
    uppy.on("upload-error", handleUploadError);
    uppy.on("complete", handleComplete);
    uppy.on("cancel-all", handleCancelAll);

    // Clean up event handlers when dependencies change
    return () => {
      uppy.off("upload", handleUpload);
      uppy.off("upload-success", handleUploadSuccess);
      uppy.off("upload-error", handleUploadError);
      uppy.off("complete", handleComplete);
      uppy.off("cancel-all", handleCancelAll);
    };
  }, [
    uppy,
    onUploadComplete,
    onUploadError,
    selectedCollections,
    selectedConnector,
    persistablePath,
    validatedCollections,
    rememberLastLocation,
  ]);
  // Keep the per-file meta the server relies on in sync with the destination, so anything
  // reading uppy.getState().meta (and Golden Retriever\'s persisted state) sees where the
  // files were headed.
  useEffect(() => {
    if (!uppy || !selectedConnector) return;
    const existingMeta = uppy.getState().meta;
    uppy.setOptions({
      meta: {
        ...existingMeta,
        connector_id: selectedConnector,
        path: uploadPath,
        collection_ids: collectionIds,
      },
    });
  }, [uppy, selectedConnector, uploadPath, collectionIds]);

  /**
   * Which dropdown entry is currently active. Derived from the destination rather than held
   * in its own state, so the control always reflects reality: browse away from a saved
   * location's path and it falls back to the plain connector entry; browse back and the
   * saved entry lights up again.
   */
  const selectedDestinationKey = useMemo(() => {
    if (!selectedConnector) return "";
    const favorite = favoriteOptions.find(
      (option) =>
        option.connectorId === selectedConnector &&
        normalizeUploadPath(option.path) === persistablePath
    );
    return favorite ? favorite.key : `conn:${selectedConnector}`;
  }, [selectedConnector, persistablePath, favoriteOptions]);

  const currentUploadLocation = useMemo<UploadLocation | null>(
    () =>
      selectedConnector
        ? {
            connectorId: selectedConnector,
            path: persistablePath,
            // Validated, not raw: saving, matching and remembering must all use one source,
            // or a saved entry could carry dead collection ids (and then warn every time it
            // is picked), and isSaved could stop matching an entry saved from a reconciled
            // state.
            collections: validatedCollections,
          }
        : null,
    [selectedConnector, persistablePath, validatedCollections]
  );

  const currentConnectorName = isMyAssetsSelected
    ? "My Assets"
    : (selectedConnectorObj?.name ?? "");

  /**
   * Whether the destination can be named yet. For a shared connector the name comes from the
   * connectors query, which is undefined until it resolves — saving before then would produce
   * an unlabelled entry, so the control is disabled rather than silently doing nothing.
   */
  const isDestinationNamed = !!currentConnectorName;

  const isCurrentLocationSaved = isSaved(currentUploadLocation);

  const handleToggleSavedLocation = () => {
    if (!currentUploadLocation || !currentConnectorName) return;
    setDroppedCollectionNotice("");
    toggleSavedLocation(currentUploadLocation);
  };

  const toggleSavedLocation = (location: UploadLocation) =>
    toggleSaved(location, currentConnectorName, selectedConnectorObj?.storageIdentifier);

  const handleDestinationChange = (event: SelectChangeEvent<string>) => {
    // Prevent destination change during active uploads
    if (isUploading) {
      console.warn("Cannot change destination while uploads are in progress");
      return;
    }

    const key = event.target.value;
    userTouchedDestinationRef.current = true;
    setDroppedCollectionNotice("");

    const favorite = favoriteOptions.find((option) => option.key === key);
    if (favorite) {
      applyUploadLocation({
        connectorId: favorite.connectorId,
        path: favorite.path,
        collections: favorite.collections,
      });
      return;
    }

    const connectorOption = connectorOptions.find((option) => option.key === key);
    if (!connectorOption) return;

    setSelectedConnector(connectorOption.connectorId);
    // Reset path when connector changes - the useEffect will auto-set to first prefix if restricted
    setUploadPath("");
  };

  // My Assets is always available independently of the connectors query, so
  // only block on the connectors load when there is no My Assets destination.
  if (isLoadingConnectors && !hasMyAssets) {
    return <Typography>{t("upload.loadingConnectors")}</Typography>;
  }

  // No destination the user can upload to (e.g. no permission to read
  // connectors and no personal My Assets space) — block uploads entirely.
  if (hasNoDestinations) {
    return (
      <Alert severity="info" icon={<InfoOutlinedIcon />}>
        {t("upload.noDestinations")}
      </Alert>
    );
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {hasSingleDestination ? (
        <Paper
          elevation={0}
          sx={{
            p: 2,
            borderRadius: "8px",
            border: "1px solid",
            borderColor: "divider",
            display: "flex",
            alignItems: "center",
            gap: 1.5,
          }}
        >
          {hasMyAssets ? (
            <>
              <PersonIcon color="primary" />
              <Typography variant="body1" sx={{ fontWeight: 600 }}>
                My Assets
              </Typography>
              <Chip label="Personal · Private" size="small" color="primary" variant="outlined" />
            </>
          ) : (
            <>
              <FolderIcon color="primary" />
              <Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
                  {t("upload.connectorLabel")}
                </Typography>
                <Typography variant="body1" sx={{ fontWeight: 600 }}>
                  {singleConnector?.name} ({singleConnector?.storageIdentifier})
                </Typography>
              </Box>
            </>
          )}
        </Paper>
      ) : (
        <FormControl fullWidth>
          <InputLabel id="connector-select-label">{t("upload.connectorLabel")}</InputLabel>
          <Select
            labelId="connector-select-label"
            id="connector-select"
            value={selectedDestinationKey}
            label={t("upload.connectorLabel")}
            onChange={handleDestinationChange}
            disabled={isUploading}
          >
            {favoriteOptions.length > 0 && (
              <ListSubheader>
                {t("upload.savedLocations.sectionTitle", "Saved locations")}
              </ListSubheader>
            )}
            {favoriteOptions.map((option) => (
              <MenuItem key={option.key} value={option.key}>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1, minWidth: 0 }}>
                  <StarIcon fontSize="small" sx={{ color: "warning.main" }} />
                  <Typography variant="body2" noWrap>
                    {option.label}
                  </Typography>
                </Box>
              </MenuItem>
            ))}

            {favoriteOptions.length > 0 && (
              <ListSubheader>
                {t("upload.savedLocations.allDestinations", "All destinations")}
              </ListSubheader>
            )}
            {connectorOptions.map((option) =>
              option.isMyAssets ? (
                <MenuItem key={option.key} value={option.key}>
                  <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                    <PersonIcon fontSize="small" color="primary" />
                    My Assets
                  </Box>
                </MenuItem>
              ) : (
                <MenuItem key={option.key} value={option.key}>
                  {option.label}
                </MenuItem>
              )
            )}
          </Select>
        </FormControl>
      )}

      {selectedConnector && (
        <CollectionSelector
          value={selectedCollections}
          onChange={setSelectedCollections}
          disabled={isUploading}
        />
      )}

      {/* Destination path and the save-location star share one row: the panel takes the
          remaining width and the star sits to its right, so the row spans the same width as
          the inputs above and the dropzone below. */}
      {selectedConnector && (
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
          {!isMyAssetsSelected && (
            <Paper
              elevation={0}
              sx={{
                p: 2,
                flex: 1,
                minWidth: 0,
                borderRadius: "8px",
                border: `1px solid`,
                borderColor: "divider",
                backgroundColor: "background.paper",
              }}
            >
              <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
                <Box sx={{ flex: 1 }}>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{ display: "block", mb: 0.5 }}
                  >
                    {t("upload.uploadDestination")}
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{
                      fontFamily: typography.monoFontFamily,
                      fontWeight: 500,
                      color: uploadPath ? "primary.main" : "text.secondary",
                    }}
                  >
                    {uploadPath || "/"}
                    {allowedPrefixes.length > 0 && (
                      <Typography
                        component="span"
                        variant="caption"
                        color="text.secondary"
                        sx={{ ml: 1 }}
                      >
                        ({t("upload.restrictedToPrefix")})
                      </Typography>
                    )}
                  </Typography>
                </Box>
                {canBrowsePaths && (
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={() => setIsPathBrowserOpen(true)}
                    disabled={!selectedConnector || isUploading}
                    startIcon={<FolderIcon />}
                    sx={{
                      textTransform: "none",
                      borderRadius: "8px",
                      minWidth: "120px",
                    }}
                  >
                    {t("upload.browsePath")}
                  </Button>
                )}
              </Box>
              {allowedPrefixes.length > 0 && (
                <Typography
                  variant="caption"
                  color="text.secondary"
                  sx={{ display: "block", mt: 1 }}
                >
                  {t("upload.allowedPrefixesInfo", {
                    count: allowedPrefixes.length,
                  })}
                </Typography>
              )}
            </Paper>
          )}

          {/* Save the whole destination — connector, path and selected collections — so it can
          be picked straight from the dropdown next time. The destination itself is already
          displayed alongside, so this is the action only. Rename/reorder and marking one as the
          default are a later phase; the last-used location is what auto-populates today. */}
          <Tooltip
            title={
              isCurrentLocationSaved
                ? t("upload.savedLocations.remove", "Remove this saved location")
                : isAtCapacity
                  ? t("upload.savedLocations.atCapacity", {
                      count: maxFavorites,
                      defaultValue: "You can save up to {{count}} locations",
                    })
                  : t("upload.savedLocations.save", "Save this location")
            }
            arrow
          >
            <span>
              <IconButton
                size="small"
                data-testid="save-upload-location-button"
                onClick={handleToggleSavedLocation}
                disabled={
                  isUploading || !isDestinationNamed || (!isCurrentLocationSaved && isAtCapacity)
                }
                aria-label={
                  isCurrentLocationSaved
                    ? t("upload.savedLocations.remove", "Remove this saved location")
                    : t("upload.savedLocations.save", "Save this location")
                }
                sx={{ color: isCurrentLocationSaved ? "warning.main" : "text.secondary" }}
              >
                {isCurrentLocationSaved ? (
                  <StarIcon fontSize="small" />
                ) : (
                  <StarBorderIcon fontSize="small" />
                )}
              </IconButton>
            </span>
          </Tooltip>
        </Box>
      )}

      {collectionWarnings.length > 0 && (
        <Alert
          severity="warning"
          data-testid="dropped-collections-notice"
          // Only offer dismissal when the message is the dismissible one. The
          // selected-collections message is derived from current state and would reappear on
          // the next render, and a close button that does nothing is worse than none.
          onClose={
            droppedCollectionNotice && droppedSelectedCollections.length === 0
              ? () => setDroppedCollectionNotice("")
              : undefined
          }
        >
          {collectionWarnings.map((message) => (
            <Typography key={message} variant="body2">
              {message}
            </Typography>
          ))}
        </Alert>
      )}

      <Box sx={{ mt: 2 }}>
        {uppy && (
          <Dashboard
            uppy={uppy}
            plugins={[]}
            width="100%"
            height={450}
            hideUploadButton={false}
            hideProgressDetails={false}
            note={t("upload.dashboardNote")}
            metaFields={[
              {
                id: "name",
                name: t("upload.meta.name"),
                placeholder: "File name",
              },
            ]}
            proudlyDisplayPoweredByUppy={false}
            disabled={!selectedConnector}
          />
        )}
      </Box>

      {selectedConnector && !isMyAssetsSelected && canBrowsePaths && (
        <PathBrowser
          open={isPathBrowserOpen}
          onClose={() => setIsPathBrowserOpen(false)}
          connectorId={selectedConnector}
          allowedPrefixes={allowedPrefixes}
          initialPath={uploadPath}
          onPathSelect={(newPath) => {
            userTouchedDestinationRef.current = true;
            // Normalize path format: ensure consistent trailing slash if not root
            const normalizedPath =
              newPath && newPath !== "/"
                ? newPath.endsWith("/")
                  ? newPath
                  : `${newPath}/`
                : newPath;
            setUploadPath(normalizedPath);
            // Call onPathChange callback if provided
            if (onPathChange) {
              onPathChange(normalizedPath);
            }
            setIsPathBrowserOpen(false);
          }}
        />
      )}
    </Box>
  );
};

export default FileUploader;
