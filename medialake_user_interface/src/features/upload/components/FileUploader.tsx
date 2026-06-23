import React, { useEffect, useState, useRef, useMemo } from "react";
import Uppy from "@uppy/core";
import Dashboard from "@uppy/react/dashboard";
import AwsS3, { type AwsS3Options } from "@uppy/aws-s3";
import "@uppy/core/css/style.min.css";
import "@uppy/dashboard/css/style.min.css";
import {
  Box,
  Button,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  SelectChangeEvent,
  Typography,
  Alert,
} from "@mui/material";
import FolderIcon from "@mui/icons-material/Folder";
import PersonIcon from "@mui/icons-material/Person";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import { useTranslation } from "react-i18next";
import { useSearchConnectors } from "@/api/hooks/useSearchConnectors";
import { usePermission } from "@/permissions";
import useS3Upload from "../hooks/useS3Upload";
import { MultipartUploadMetadata } from "../types/upload.types";
import PathBrowser from "./PathBrowser";
import CollectionSelector, { CollectionRef } from "./CollectionSelector";
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
        "application/mxf"
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
  const [uppy, setUppy] = useState<Uppy<Meta> | null>(null);
  const [selectedConnector, setSelectedConnector] = useState<string>("");
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadPath, setUploadPath] = useState<string>(path || "");
  const [isPathBrowserOpen, setIsPathBrowserOpen] = useState<boolean>(false);
  const [selectedCollections, setSelectedCollections] = useState<CollectionRef[]>([]);
  const { data: connectorsResponse, isLoading: isLoadingConnectors } = useSearchConnectors();
  const {
    getPresignedUrl,
    signPart: signPartBackend,
    completeMultipartUpload,
    abortMultipartUpload,
  } = useS3Upload();

  // Store multipart upload metadata keyed by file ID
  const multipartDataRef = useRef<Map<string, MultipartUploadMetadata>>(new Map());

  // Filter only S3 connectors that are active and have uploads enabled
  const connectors =
    connectorsResponse?.data?.connectors.filter(
      (connector) =>
        connector.type === "s3" &&
        connector.status === "active" &&
        connector.configuration?.allowUploads !== false
    ) || [];

  // Memoize collection ids for the upload request body and Uppy meta
  const collectionIds = useMemo(() => selectedCollections.map((c) => c.id), [selectedCollections]);

  // Connectors the user can pick from, excluding the My Assets virtual connector.
  // When the connector is locked (e.g. "Upload to My Assets"), or the user
  // lacks the connectors:upload permission, no other connectors are selectable
  // — only My Assets remains available.
  const otherConnectors = connectors.filter((c) => c.id !== defaultConnectorId);
  const selectableConnectors = lockConnector || !canUploadToConnectors ? [] : otherConnectors;

  // My Assets is a valid destination only when a defaultConnectorId is provided.
  const hasMyAssets = !!defaultConnectorId;

  // Total destinations available to the user. If the user can't read any
  // connectors (e.g. no permission) and has no personal My Assets space,
  // this is 0 and uploads are blocked.
  const destinationCount = (hasMyAssets ? 1 : 0) + selectableConnectors.length;
  const hasNoDestinations = destinationCount === 0;
  const hasSingleDestination = destinationCount === 1;

  // The single connector destination (when My Assets is not present).
  const singleConnector = !hasMyAssets ? selectableConnectors[0] : undefined;

  // When there is exactly one selectable connector and no My Assets, that
  // connector is auto-selected (no dropdown is shown).
  const autoSelectConnectorId =
    !hasMyAssets && selectableConnectors.length === 1 ? selectableConnectors[0].id : undefined;

  // Sync uploadPath with path prop
  useEffect(() => {
    setUploadPath(path || "");
  }, [path]);

  // Pre-select the destination automatically:
  // - My Assets when a defaultConnectorId is provided
  // - the only connector when it is the single available destination
  useEffect(() => {
    if (defaultConnectorId) {
      setSelectedConnector(defaultConnectorId);
    } else if (autoSelectConnectorId) {
      setSelectedConnector(autoSelectConnectorId);
    }
  }, [defaultConnectorId, autoSelectConnectorId]);

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
  const allowedPrefixes = useMemo(() => {
    const topLevelPrefix = selectedConnectorObj?.objectPrefix;
    const configPrefix = selectedConnectorObj?.configuration?.objectPrefix;
    const prefixToUse = topLevelPrefix !== undefined ? topLevelPrefix : configPrefix;
    return parseObjectPrefix(prefixToUse);
  }, [selectedConnectorObj]);

  // Automatically default to first allowed prefix when connector has restrictions
  // For My Assets, use the fixed defaultObjectPrefix
  useEffect(() => {
    if (isMyAssetsSelected && defaultObjectPrefix) {
      const normalizedPrefix = defaultObjectPrefix.endsWith("/")
        ? defaultObjectPrefix
        : `${defaultObjectPrefix}/`;
      setUploadPath(normalizedPrefix);
      if (onPathChange) {
        onPathChange(normalizedPrefix);
      }
      return;
    }
    if (selectedConnector && allowedPrefixes.length > 0 && (!uploadPath || uploadPath === "/")) {
      const firstPrefix = allowedPrefixes[0];
      const normalizedPrefix = firstPrefix.endsWith("/") ? firstPrefix : `${firstPrefix}/`;
      setUploadPath(normalizedPrefix);
      if (onPathChange) {
        onPathChange(normalizedPrefix);
      }
    }
  }, [
    selectedConnector,
    allowedPrefixes,
    uploadPath,
    onPathChange,
    isMyAssetsSelected,
    defaultObjectPrefix,
  ]);

  // Initialize Uppy when the component mounts
  useEffect(() => {
    if (typeof window === "undefined") return;

    // Create Uppy instance
    const uppyInstance = getUppy();

    // Validate filenames
    uppyInstance.on("file-added", (file) => {
      if (!FILENAME_REGEX.test(file.name)) {
        uppyInstance.info(
          `Filename "${file.name}" contains characters not supported by S3. Avoid: \\ { } ^ \` ~ | % < > " # [ ]`, // i18n-ignore
          "error",
          5000
        );
        uppyInstance.removeFile(file.id);
      }
    });

    // Add AWS S3 plugin with multipart support
    uppyInstance.use(AwsS3, {
      id: "S3Uploader",
      // Concurrent file uploads — kept conservative since S3 uses HTTP/1.1
      // and each multipart file generates many sign requests
      limit: 6,
      // Scale chunk size with file size to reduce sign round-trips.
      // Each chunk requires a sign API call (~2-3s) so fewer, larger chunks
      // dramatically reduce overhead for big files.
      getChunkSize: (file: { size: number }) => {
        const GB = 1024 * 1024 * 1024;
        const MB = 1024 * 1024;
        if (file.size >= 100 * GB) return 500 * MB; // 100GB+ → 500MB chunks (~200-1000 parts)
        if (file.size >= 10 * GB) return 200 * MB; // 10-100GB → 200MB chunks
        if (file.size >= 1 * GB) return 100 * MB; // 1-10GB → 100MB chunks (~10-100 parts)
        if (file.size >= 100 * MB) return 50 * MB; // 100MB-1GB → 50MB chunks
        return 5 * MB; // <100MB → 5MB chunks (S3 minimum)
      },
      // More aggressive retries for large/long uploads
      retryDelays: [0, 1000, 3000, 5000, 10000],
    } as any);

    setUppy(uppyInstance);

    // Clean up function
    return () => {
      if (uppyInstance) {
        try {
          // Cancel any ongoing uploads and remove all files
          uppyInstance.cancelAll();

          // Clean up multipart metadata
          multipartDataRef.current.clear();
        } catch (e) {
          console.error("Error cleaning up Uppy instance:", e);
        }
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
  }, [uppy, onUploadComplete, onUploadError, selectedCollections]);

  // Configure S3 upload when connector is selected
  useEffect(() => {
    if (!uppy || !selectedConnector) return;

    // Merge new meta with existing meta to avoid clobbering future meta fields
    const existingMeta = uppy.getState().meta;
    uppy.setOptions({
      meta: {
        ...existingMeta,
        connector_id: selectedConnector,
        path: uploadPath,
        collection_ids: collectionIds,
      },
    });

    // Configure S3 upload parameters with multipart support
    // Works for both regular S3 connectors and My Assets virtual connectors
    const awsS3 = uppy.getPlugin("S3Uploader") as typeof AwsS3.prototype;
    if (awsS3) {
      try {
        const options: Partial<AwsS3Options<Meta, Record<string, never>>> = {
          // Enable multipart upload for files larger than 100MB
          shouldUseMultipart: (file) => file.size > 100 * 1024 * 1024,

          // Get upload parameters from backend (single-part presigned POST only)
          getUploadParameters: async (file: any) => {
            try {
              const result = await getPresignedUrl({
                connector_id: selectedConnector,
                filename: file.name,
                content_type: file.type,
                file_size: file.size,
                path: uploadPath,
                collection_ids: collectionIds,
              });

              // Single-part upload
              if (!result.presigned_post) {
                throw new Error("Missing presigned post data");
              }

              return {
                method: "POST" as const,
                url: result.presigned_post.url,
                fields: result.presigned_post.fields,
              };
            } catch (error) {
              console.error("Error getting upload parameters:", error);
              throw error;
            }
          },

          // Create multipart upload - calls backend and stores metadata
          createMultipartUpload: async (file: any) => {
            try {
              const result = await getPresignedUrl({
                connector_id: selectedConnector,
                filename: file.name,
                content_type: file.type,
                file_size: file.size,
                path: uploadPath,
                collection_ids: collectionIds,
              });

              if (!result.multipart) {
                throw new Error(
                  `Expected multipart upload for file ${file.name}, but backend returned single-part.`
                );
              }

              if (!result.upload_id || !result.key || !result.bucket) {
                throw new Error(`Missing required multipart data for file ${file.name}.`);
              }

              // Store multipart data for later use in signPart (on-demand)
              multipartDataRef.current.set(file.id, {
                uploadId: result.upload_id,
                key: result.key,
                bucket: result.bucket,
                connector_id: selectedConnector,
              });

              return {
                uploadId: result.upload_id,
                key: result.key,
              };
            } catch (error) {
              console.error("Error creating multipart upload:", error);
              throw error;
            }
          },

          // Sign individual parts on-demand - calls backend for each part
          signPart: async (file: any, partData: any) => {
            const data = multipartDataRef.current.get(file.id);
            if (!data) {
              throw new Error(
                `Multipart data not found for file ${file.name}. Please try uploading again or contact support if the issue persists.`
              );
            }

            const partNumber = partData.partNumber;

            try {
              // Call backend to sign this specific part on-demand
              const signResponse = await signPartBackend({
                connector_id: data.connector_id,
                upload_id: data.uploadId,
                key: data.key,
                part_number: partNumber,
              });

              return {
                url: signResponse.presigned_url,
              };
            } catch (error) {
              console.error(`Failed to sign part ${partNumber} for ${file.name}:`, error);
              throw error;
            }
          },

          // Complete multipart upload - calls backend to finalize
          completeMultipartUpload: async (file: any, data: any) => {
            const multipartData = multipartDataRef.current.get(file.id);
            if (!multipartData) {
              throw new Error(
                `Multipart data not found for file ${file.name}. Please try uploading again or contact support if the issue persists.`
              );
            }

            try {
              const result = await completeMultipartUpload({
                connector_id: selectedConnector,
                upload_id: multipartData.uploadId,
                key: multipartData.key,
                parts: data.parts,
              });

              // Clean up stored metadata
              multipartDataRef.current.delete(file.id);

              return {
                location: result.location,
              };
            } catch (error) {
              console.error(`Error completing multipart upload for ${file.name}:`, error);
              multipartDataRef.current.delete(file.id);
              throw error;
            }
          },

          // Abort multipart upload - calls backend to abort
          abortMultipartUpload: async (file: any) => {
            const multipartData = multipartDataRef.current.get(file.id);
            if (multipartData) {
              try {
                await abortMultipartUpload({
                  connector_id: selectedConnector,
                  upload_id: multipartData.uploadId,
                  key: multipartData.key,
                });
              } catch (error) {
                console.error(`Error aborting multipart upload for ${file.name}:`, error);
              }
              // Clean up stored metadata regardless of abort success
              multipartDataRef.current.delete(file.id);
            }
          },
        };

        awsS3.setOptions(options);
      } catch (error) {
        console.error("Error configuring S3 plugin:", error);
      }
    }
  }, [
    uppy,
    selectedConnector,
    getPresignedUrl,
    completeMultipartUpload,
    abortMultipartUpload,
    uploadPath,
    collectionIds,
  ]);

  const handleConnectorChange = (event: SelectChangeEvent<string>) => {
    // Prevent connector change during active uploads
    if (isUploading) {
      console.warn("Cannot change connector while uploads are in progress");
      return;
    }
    setSelectedConnector(event.target.value);
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
            value={selectedConnector}
            label={t("upload.connectorLabel")}
            onChange={handleConnectorChange}
            disabled={isUploading}
          >
            {hasMyAssets && (
              <MenuItem value={defaultConnectorId}>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                  <PersonIcon fontSize="small" color="primary" />
                  My Assets
                </Box>
              </MenuItem>
            )}
            {selectableConnectors.map((connector) => (
              <MenuItem key={connector.id} value={connector.id}>
                {connector.name} ({connector.storageIdentifier})
              </MenuItem>
            ))}
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

      {selectedConnector && !isMyAssetsSelected && (
        <Paper
          elevation={0}
          sx={{
            p: 2,
            mb: 2,
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
          </Box>
          {allowedPrefixes.length > 0 && (
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 1 }}>
              {t("upload.allowedPrefixesInfo", {
                count: allowedPrefixes.length,
              })}
            </Typography>
          )}
        </Paper>
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

      {selectedConnector && !isMyAssetsSelected && (
        <PathBrowser
          open={isPathBrowserOpen}
          onClose={() => setIsPathBrowserOpen(false)}
          connectorId={selectedConnector}
          allowedPrefixes={allowedPrefixes}
          initialPath={uploadPath}
          onPathSelect={(newPath) => {
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
