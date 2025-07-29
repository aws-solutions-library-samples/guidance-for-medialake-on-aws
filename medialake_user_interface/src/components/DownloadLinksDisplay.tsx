import React from "react";
import { Box, Link, Typography, Chip, Stack, Divider } from "@mui/material";
import {
  Download as DownloadIcon,
  Archive as ArchiveIcon,
  InsertDriveFile as FileIcon,
} from "@mui/icons-material";

interface DownloadLinksDisplayProps {
  downloadUrls:
    | {
        zippedFiles?: string;
        files?: string[];
        singleFiles?: string[];
      }
    | string[];
  expiresAt?: string;
  description?: string;
}

export const DownloadLinksDisplay: React.FC<DownloadLinksDisplayProps> = ({
  downloadUrls,
  expiresAt,
  description,
}) => {
  // Check if links have expired
  const isExpired = React.useMemo(() => {
    if (!expiresAt) return false;

    // Handle Unix timestamp (string of numbers) or ISO date string
    const timestamp = /^\d+$/.test(expiresAt)
      ? parseInt(expiresAt, 10) * 1000
      : expiresAt;
    const expirationDate = new Date(timestamp);

    if (isNaN(expirationDate.getTime())) return false;

    return new Date() > expirationDate;
  }, [expiresAt]);

  // Format expiration date
  const formatExpirationDate = React.useCallback((expiresAt: string) => {
    const timestamp = /^\d+$/.test(expiresAt)
      ? parseInt(expiresAt, 10) * 1000
      : expiresAt;
    const date = new Date(timestamp);
    return isNaN(date.getTime()) ? "Unknown" : date.toLocaleString();
  }, []);
  // Handle legacy format (array of URLs)
  if (Array.isArray(downloadUrls)) {
    return (
      <Box sx={{ mt: 1 }}>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          Download Links:
        </Typography>
        <Stack spacing={0.5}>
          {downloadUrls.map((url, index) => (
            <Link
              key={index}
              href={isExpired ? undefined : url}
              target="_blank"
              rel="noopener noreferrer"
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 0.5,
                fontSize: "0.875rem",
                textDecoration: "none",
                color: isExpired ? "text.disabled" : "primary.main",
                cursor: isExpired ? "not-allowed" : "pointer",
                opacity: isExpired ? 0.5 : 1,
                "&:hover": {
                  textDecoration: isExpired ? "none" : "underline",
                },
              }}
              onClick={isExpired ? (e) => e.preventDefault() : undefined}
            >
              <DownloadIcon fontSize="small" />
              Download {index + 1} {isExpired && "(EXPIRED)"}
            </Link>
          ))}
        </Stack>
        {expiresAt && (
          <Typography
            variant="caption"
            color={isExpired ? "error.main" : "warning.main"}
            sx={{
              mt: 1,
              display: "block",
              fontWeight: isExpired ? "bold" : "normal",
            }}
          >
            {isExpired ? "EXPIRED: " : "Expires: "}
            {formatExpirationDate(expiresAt)}
          </Typography>
        )}
      </Box>
    );
  }

  // Handle new structured format
  const { zippedFiles, files = [], singleFiles = [] } = downloadUrls;
  const hasDownloads =
    zippedFiles || files.length > 0 || singleFiles.length > 0;

  if (!hasDownloads) {
    return null;
  }

  return (
    <Box sx={{ mt: 1 }}>
      {description && (
        <Typography variant="body2" color="text.secondary" gutterBottom>
          {description}
        </Typography>
      )}

      <Stack spacing={1} sx={{ mt: 1 }}>
        {/* Zipped Files */}
        {zippedFiles && (
          <Box>
            <Link
              href={isExpired ? undefined : zippedFiles}
              target="_blank"
              rel="noopener noreferrer"
              sx={{
                display: "flex",
                alignItems: "center",
                gap: 0.5,
                fontSize: "0.875rem",
                textDecoration: "none",
                color: isExpired ? "text.disabled" : "primary.main",
                cursor: isExpired ? "not-allowed" : "pointer",
                opacity: isExpired ? 0.5 : 1,
                "&:hover": {
                  textDecoration: isExpired ? "none" : "underline",
                },
              }}
              onClick={isExpired ? (e) => e.preventDefault() : undefined}
            >
              <ArchiveIcon fontSize="small" />
              Download ZIP Archive {isExpired && "(EXPIRED)"}
            </Link>
          </Box>
        )}

        {/* Individual Files */}
        {files.length > 0 && (
          <Box>
            {zippedFiles && <Divider sx={{ my: 0.5 }} />}
            <Typography variant="caption" color="text.secondary" gutterBottom>
              Individual Files:
            </Typography>
            <Stack spacing={0.5}>
              {files.map((url, index) => (
                <Link
                  key={index}
                  href={isExpired ? undefined : url}
                  target="_blank"
                  rel="noopener noreferrer"
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    gap: 0.5,
                    fontSize: "0.875rem",
                    textDecoration: "none",
                    color: isExpired ? "text.disabled" : "primary.main",
                    cursor: isExpired ? "not-allowed" : "pointer",
                    opacity: isExpired ? 0.5 : 1,
                    "&:hover": {
                      textDecoration: isExpired ? "none" : "underline",
                    },
                  }}
                  onClick={isExpired ? (e) => e.preventDefault() : undefined}
                >
                  <FileIcon fontSize="small" />
                  File {index + 1} {isExpired && "(EXPIRED)"}
                </Link>
              ))}
            </Stack>
          </Box>
        )}

        {/* Single Files */}
        {singleFiles.length > 0 && (
          <Box>
            {(zippedFiles || files.length > 0) && <Divider sx={{ my: 0.5 }} />}
            <Stack spacing={0.5}>
              {singleFiles.map((url, index) => (
                <Link
                  key={index}
                  href={isExpired ? undefined : url}
                  target="_blank"
                  rel="noopener noreferrer"
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    gap: 0.5,
                    fontSize: "0.875rem",
                    textDecoration: "none",
                    color: isExpired ? "text.disabled" : "primary.main",
                    cursor: isExpired ? "not-allowed" : "pointer",
                    opacity: isExpired ? 0.5 : 1,
                    "&:hover": {
                      textDecoration: isExpired ? "none" : "underline",
                    },
                  }}
                  onClick={isExpired ? (e) => e.preventDefault() : undefined}
                >
                  <DownloadIcon fontSize="small" />
                  Download File {index + 1} {isExpired && "(EXPIRED)"}
                </Link>
              ))}
            </Stack>
          </Box>
        )}
      </Stack>

      {/* Expiration Warning */}
      {expiresAt && (
        <Box sx={{ mt: 1 }}>
          <Chip
            label={`${isExpired ? "EXPIRED: " : "Expires: "}${formatExpirationDate(expiresAt)}`}
            size="small"
            color={isExpired ? "error" : "warning"}
            variant={isExpired ? "filled" : "outlined"}
            sx={{
              fontSize: "0.75rem",
              fontWeight: isExpired ? "bold" : "normal",
              animation: isExpired ? "pulse 2s infinite" : "none",
              "@keyframes pulse": {
                "0%": { opacity: 1 },
                "50%": { opacity: 0.7 },
                "100%": { opacity: 1 },
              },
            }}
          />
        </Box>
      )}
    </Box>
  );
};
