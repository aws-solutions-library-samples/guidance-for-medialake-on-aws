import React, { useEffect, useState, useRef, useMemo } from "react";
import Uppy from "@uppy/core";
import Dashboard from "@uppy/react/dashboard";
import AwsS3, { type AwsS3Options } from "@uppy/aws-s3";
import "@uppy/core/css/style.min.css";
import "@uppy/dashboard/css/style.min.css";
import {
  Box,
  Button,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  SelectChangeEvent,
  Typography,
} from "@mui/material";
import FolderIcon from "@mui/icons-material/Folder";
import { useTranslation } from "react-i18next";
import { useGetConnectors } from "@/api/hooks/useConnectors";
import useS3Upload from "../hooks/useS3Upload";
import { MultipartUploadMetadata } from "../types/upload.types";
import PathBrowser from "./PathBrowser";

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
      maxFileSize: 10 * 1024 * 1024 * 1024, // 10GB max file size
      allowedFileTypes: [
        "audio/*",
        "video/*",
        "image/*",
        "application/x-mpegURL", // HLS
        "application/dash+xml", // MPEG-DASH
      ],
      maxNumberOfFiles: 10,
    },
  });
}

// Regex pattern for S3-compatible filenames
const FILENAME_REGEX = /^[a-zA-Z0-9!\-_.*'()]+$/;

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
}

const FileUploader: React.FC<FileUploaderProps> = ({
  onUploadComplete,
  onUploadError,
  path = "",
  onPathChange,
}) => {
  const { t } = useTranslation();
  const [uppy, setUppy] = useState<Uppy<Meta> | null>(null);
  const [selectedConnector, setSelectedConnector] = useState<string>("");
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadPath, setUploadPath] = useState<string>(path || "");
  const [isPathBrowserOpen, setIsPathBrowserOpen] = useState<boolean>(false);
  const { data: connectorsResponse, isLoading: isLoadingConnectors } = useGetConnectors();
  const {
    getPresignedUrl,
    signPart: signPartBackend,
    completeMultipartUpload,
    abortMultipartUpload,
  } = useS3Upload();

  // Store multipart upload metadata keyed by file ID
  const multipartDataRef = useRef<Map<string, MultipartUploadMetadata>>(new Map());

  // Filter only S3 connectors that are active
  const connectors =
    connectorsResponse?.data?.connectors.filter(
      (connector) => connector.type === "s3" && connector.status === "active"
    ) || [];

  // Sync uploadPath with path prop
  useEffect(() => {
    setUploadPath(path || "");
  }, [path]);

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

  // Extract and parse allowedPrefixes from selected connector
  // Fallback to configuration.objectPrefix if top-level objectPrefix is undefined
  const allowedPrefixes = useMemo(() => {
    const topLevelPrefix = selectedConnectorObj?.objectPrefix;
    const configPrefix = selectedConnectorObj?.configuration?.objectPrefix;
    const prefixToUse = topLevelPrefix !== undefined ? topLevelPrefix : configPrefix;
    return parseObjectPrefix(prefixToUse);
  }, [selectedConnectorObj]);

  // Automatically default to first allowed prefix when connector has restrictions
  // This prevents users from seeing "/" as the destination when they can't upload there
  useEffect(() => {
    // Only auto-set path if:
    // 1. A connector is selected
    // 2. The connector has prefix restrictions (allowedPrefixes.length > 0)
    // 3. The current uploadPath is empty or root ("/")
    if (selectedConnector && allowedPrefixes.length > 0 && (!uploadPath || uploadPath === "/")) {
      const firstPrefix = allowedPrefixes[0];
      // Ensure the prefix has proper formatting (trailing slash)
      const normalizedPrefix = firstPrefix.endsWith("/") ? firstPrefix : `${firstPrefix}/`;

      setUploadPath(normalizedPrefix);

      // Notify parent component if callback provided
      if (onPathChange) {
        onPathChange(normalizedPrefix);
      }
    }
  }, [selectedConnector, allowedPrefixes, uploadPath, onPathChange]);

  // Initialize Uppy when the component mounts
  useEffect(() => {
    if (typeof window === "undefined") return;

    // Create Uppy instance
    const uppyInstance = getUppy();

    // Validate filenames
    uppyInstance.on("file-added", (file) => {
      if (!FILENAME_REGEX.test(file.name)) {
        uppyInstance.info(
          `Filename "${file.name}" contains invalid characters. Only alphanumeric characters, dashes, underscores, dots, exclamation marks, asterisks, single quotes, and parentheses are allowed.`,
          "error",
          5000
        );
        uppyInstance.removeFile(file.id);
      }
    });

    // Add AWS S3 plugin with multipart support
    uppyInstance.use(AwsS3, {
      id: "S3Uploader",
      limit: 5, // concurrent uploads (as per requirements)
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

    const handleUploadSuccess = (file: any, response: any) => {
      console.log("Upload complete:", file.name, response);
    };

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
      console.log("Upload complete:", result.successful);
      setIsUploading(false);
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
  }, [uppy, onUploadComplete, onUploadError]);

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
      },
    });

    // Find the selected connector
    const connector = connectors.find((c) => c.id === selectedConnector);
    if (!connector) return;

    // Configure S3 upload parameters with multipart support
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

              console.log(`Creating multipart upload for ${file.name}:`, {
                uploadId: result.upload_id,
                key: result.key,
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

            console.log(`Requesting presigned URL for part ${partNumber} of ${file.name}`);

            try {
              // Call backend to sign this specific part on-demand
              const signResponse = await signPartBackend({
                connector_id: data.connector_id,
                upload_id: data.uploadId,
                key: data.key,
                part_number: partNumber,
              });

              console.log(`Part ${partNumber} signed successfully for ${file.name}`);

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

              console.log(`Multipart upload completed for ${file.name}:`, result);

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
                console.log(`Multipart upload aborted for ${file.name}`);
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
    connectors,
    getPresignedUrl,
    completeMultipartUpload,
    abortMultipartUpload,
    uploadPath,
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

  if (isLoadingConnectors) {
    return <Typography>{t("upload.loadingConnectors")}</Typography>;
  }

  if (connectors.length === 0) {
    return <Typography color="error">{t("upload.noConnectors")}</Typography>;
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <FormControl fullWidth>
        <InputLabel id="connector-select-label">{t("upload.connectorLabel")}</InputLabel>
        <Select
          labelId="connector-select-label"
          id="connector-select"
          value={selectedConnector}
          label={t("upload.connectorLabel")}
          onChange={handleConnectorChange}
          disabled={!connectors.length || isUploading}
        >
          <MenuItem value="" disabled>
            <em>{t("upload.selectConnectorPlaceholder")}</em>
          </MenuItem>
          {connectors.map((connector) => (
            <MenuItem key={connector.id} value={connector.id}>
              {connector.name} ({connector.storageIdentifier})
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      {selectedConnector && (
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
                  fontFamily: "monospace",
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

      {selectedConnector && (
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
