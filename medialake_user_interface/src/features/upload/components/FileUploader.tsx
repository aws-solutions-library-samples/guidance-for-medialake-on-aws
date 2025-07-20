import React, { useEffect, useState } from "react";
import Uppy from "@uppy/core";
import { Dashboard } from "@uppy/react";
import "@uppy/core/dist/style.min.css";
import "@uppy/dashboard/dist/style.min.css";
import "@uppy/status-bar/dist/style.min.css";
import "@uppy/progress-bar/dist/style.min.css";
import {
  Box,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  SelectChangeEvent,
  Typography,
} from "@mui/material";
import { useGetConnectors } from "@/api/hooks/useConnectors";
import useS3Upload from "../hooks/useS3Upload";

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

// Safe plugin loader functions that return properly typed plugins
function getAwsS3Plugin() {
  if (typeof window === "undefined") return null;
  return require("@uppy/aws-s3").default;
}

function getAwsS3MultipartPlugin() {
  if (typeof window === "undefined") return null;
  return require("@uppy/aws-s3-multipart").default;
}

function getProgressBarPlugin() {
  if (typeof window === "undefined") return null;
  return require("@uppy/progress-bar").default;
}

// Regex pattern for S3-compatible filenames
const FILENAME_REGEX = /^[a-zA-Z0-9!\-_.*'()]+$/;

interface FileUploaderProps {
  onUploadComplete?: (files: any[]) => void;
  onUploadError?: (error: Error, file: any) => void;
  path?: string;
}

const FileUploader: React.FC<FileUploaderProps> = ({
  onUploadComplete,
  onUploadError,
  path = "",
}) => {
  const [uppy, setUppy] = useState<Uppy<any> | null>(null);
  const [selectedConnector, setSelectedConnector] = useState<string>("");
  const { data: connectorsResponse, isLoading: isLoadingConnectors } =
    useGetConnectors();
  const { getPresignedUrl } = useS3Upload();

  // Filter only S3 connectors that are active
  const connectors =
    connectorsResponse?.data?.connectors.filter(
      (connector) => connector.type === "s3" && connector.status === "active",
    ) || [];

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
          5000,
        );
        uppyInstance.removeFile(file.id);
      }
    });

    try {
      // Add plugins safely
      const ProgressBar = getProgressBarPlugin();
      if (ProgressBar) {
        // @ts-ignore - Intentionally ignoring type issues with plugins
        uppyInstance.use(ProgressBar, {
          id: "S3ProgressBar",
          fixed: false,
          hideAfterFinish: false,
        });
      }

      const AwsS3 = getAwsS3Plugin();
      if (AwsS3) {
        // @ts-ignore - Intentionally ignoring type issues with plugins
        uppyInstance.use(AwsS3, {
          id: "S3Uploader",
          limit: 5, // concurrent uploads (as per requirements)
        });
      }

      const AwsS3Multipart = getAwsS3MultipartPlugin();
      if (AwsS3Multipart) {
        // @ts-ignore - Intentionally ignoring type issues with plugins
        uppyInstance.use(AwsS3Multipart, {
          id: "S3MultipartUploader",
          limit: 5, // concurrent uploads
          allowedMetaFields: ["connector_id"],
          createMultipartUpload: async () => ({ uploadId: "", key: "" }),
          listParts: async () => [],
          prepareUploadParts: async () => [],
          abortMultipartUpload: async () => {},
          completeMultipartUpload: async () => ({ location: "" }),
        });
      }
    } catch (error) {
      console.error("Error initializing Uppy plugins:", error);
    }

    setUppy(uppyInstance);

    // Clean up function
    return () => {
      if (uppyInstance) {
        // Cancel any ongoing uploads
        uppyInstance.cancelAll();

        // Remove all files from Uppy
        try {
          // This is the correct method to remove all files
          uppyInstance.cancelAll();
          uppyInstance.getFiles().forEach((file) => {
            uppyInstance.removeFile(file.id);
          });
        } catch (e) {
          console.error("Error cleaning up Uppy instance:", e);
        }
      }
    };
  }, []);

  // Set up event handlers
  useEffect(() => {
    if (!uppy) return;

    const handleUploadSuccess = (file: any, response: any) => {
      console.log("Upload complete:", file.name, response);
    };

    const handleUploadError = (file: any, error: Error) => {
      console.error("Upload error:", file.name, error);
      if (onUploadError) {
        onUploadError(error, file);
      }
    };

    const handleComplete = (result: { successful: any[] }) => {
      console.log("Upload complete:", result.successful);
      if (onUploadComplete) {
        onUploadComplete(result.successful);
      }
    };

    uppy.on("upload-success", handleUploadSuccess);
    uppy.on("upload-error", handleUploadError);
    uppy.on("complete", handleComplete);

    // Clean up event handlers when dependencies change
    return () => {
      uppy.off("upload-success", handleUploadSuccess);
      uppy.off("upload-error", handleUploadError);
      uppy.off("complete", handleComplete);
    };
  }, [uppy, onUploadComplete, onUploadError]);

  // Configure S3 upload when connector is selected
  useEffect(() => {
    if (!uppy || !selectedConnector) return;

    // Set connector_id in meta
    uppy.setOptions({
      meta: {
        connector_id: selectedConnector,
      },
    });

    // Find the selected connector
    const connector = connectors.find((c) => c.id === selectedConnector);
    if (!connector) return;

    // Configure S3 upload parameters
    const awsS3 = uppy.getPlugin("S3Uploader");
    if (awsS3) {
      try {
        // @ts-ignore - Plugin type incompatibility
        awsS3.setOptions({
          getUploadParameters: async (file: any) => {
            try {
              const result = await getPresignedUrl({
                connector_id: selectedConnector,
                filename: file.name,
                content_type: file.type,
                file_size: file.size,
                path,
              });

              if (result.multipart) {
                // For multipart uploads, configure the multipart plugin
                const s3MultipartPlugin = uppy.getPlugin("S3MultipartUploader");
                if (s3MultipartPlugin) {
                  // @ts-ignore - Plugin type incompatibility
                  s3MultipartPlugin.setOptions({
                    companionUrl: null,
                    createMultipartUpload: async () => {
                      return {
                        uploadId: result.upload_id,
                        key: result.key,
                      };
                    },
                    listParts: async () => [],
                    prepareUploadParts: async (partData: any) => {
                      const { partNumbers } = partData;
                      return partNumbers.map((partNumber: number) => {
                        const partUrlData = result.part_urls?.find(
                          (p) => p.part_number === partNumber,
                        );
                        return {
                          url: partUrlData?.presigned_url,
                          headers: {},
                        };
                      });
                    },
                    abortMultipartUpload: async () => {},
                    completeMultipartUpload: async () => {
                      return {
                        location: `s3://${result.bucket}/${result.key}`,
                      };
                    },
                  });
                }
                throw new Error(
                  "Please use multipart upload for this file size",
                );
              }

              if (!result.presigned_post) {
                throw new Error("Missing presigned post data");
              }

              return {
                method: "POST",
                url: result.presigned_post.url,
                fields: result.presigned_post.fields,
                headers: {
                  "Content-Type": file.type,
                },
              };
            } catch (error) {
              console.error("Error getting upload parameters:", error);
              throw error;
            }
          },
        });
      } catch (error) {
        console.error("Error configuring S3 plugin:", error);
      }
    }
  }, [uppy, selectedConnector, connectors, getPresignedUrl, path]);

  const handleConnectorChange = (event: SelectChangeEvent<string>) => {
    setSelectedConnector(event.target.value);
  };

  if (isLoadingConnectors) {
    return <Typography>Loading connectors...</Typography>;
  }

  if (connectors.length === 0) {
    return (
      <Typography color="error">
        No S3 connectors available. Please configure an S3 connector first.
      </Typography>
    );
  }

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <FormControl fullWidth>
        <InputLabel id="connector-select-label">S3 Connector</InputLabel>
        <Select
          labelId="connector-select-label"
          id="connector-select"
          value={selectedConnector}
          label="S3 Connector"
          onChange={handleConnectorChange}
          disabled={!connectors.length}
        >
          <MenuItem value="" disabled>
            <em>Select an S3 connector</em>
          </MenuItem>
          {connectors.map((connector) => (
            <MenuItem key={connector.id} value={connector.id}>
              {connector.name} ({connector.storageIdentifier})
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      <Box sx={{ mt: 2 }}>
        {/* Progress bar container */}
        <Box sx={{ mb: 2 }} id="progress-bar-container"></Box>

        {uppy && (
          <Dashboard
            uppy={uppy}
            plugins={[]}
            width="100%"
            height={450}
            showProgressDetails
            note="Only audio, video, images, HLS (application/x-mpegURL), and MPEG-DASH (application/dash+xml) files are allowed"
            metaFields={[
              { id: "name", name: "Name", placeholder: "File name" },
            ]}
            proudlyDisplayPoweredByUppy={false}
            disabled={!selectedConnector}
          />
        )}
      </Box>
    </Box>
  );
};

export default FileUploader;
