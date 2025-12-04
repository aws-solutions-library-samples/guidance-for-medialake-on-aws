import React, { useState, useEffect, useCallback, useMemo } from "react";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Paper,
  Box,
  Alert,
  Typography,
  useTheme,
  useMediaQuery,
  alpha,
} from "@mui/material";
import { S3Explorer } from "../../home/S3Explorer";

interface PathBrowserProps {
  open: boolean;
  onClose: () => void;
  connectorId: string;
  allowedPrefixes?: string[];
  onPathSelect: (path: string) => void;
  initialPath?: string;
}

export const PathBrowser: React.FC<PathBrowserProps> = ({
  open,
  onClose,
  connectorId,
  allowedPrefixes,
  onPathSelect,
  initialPath,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("md"));

  // State management
  const [selectedPrefix, setSelectedPrefix] = useState<string>("");
  const [currentBrowsePath, setCurrentBrowsePath] = useState<string>("");
  const [validationError, setValidationError] = useState<string>("");

  // Parse and normalize allowed prefixes
  const normalizedPrefixes = useMemo(() => {
    if (!allowedPrefixes || allowedPrefixes.length === 0) {
      return [];
    }
    // Normalize prefixes by ensuring they end with /
    return allowedPrefixes.map((prefix) => {
      const normalized = prefix.trim();
      return normalized.endsWith("/") ? normalized : `${normalized}/`;
    });
  }, [allowedPrefixes]);

  // Determine if we're in restricted mode
  const isRestrictedMode = normalizedPrefixes.length > 0;

  // Initialize state when dialog opens or props change
  useEffect(() => {
    if (open) {
      if (initialPath !== undefined) {
        // Normalize initialPath: treat '' and '/' as equivalent for root
        const normalizedInitial = initialPath === "/" ? "" : initialPath;
        setCurrentBrowsePath(normalizedInitial);

        // In restricted mode, set selectedPrefix based on initialPath
        if (isRestrictedMode) {
          const normalizedPath = normalizedInitial.endsWith("/")
            ? normalizedInitial
            : `${normalizedInitial}/`;

          // Find the longest matching prefix
          let longestMatch = "";
          for (const prefix of normalizedPrefixes) {
            if (normalizedPath.startsWith(prefix) && prefix.length > longestMatch.length) {
              longestMatch = prefix;
            }
          }

          if (longestMatch) {
            // Set selectedPrefix to the longest matching prefix
            setSelectedPrefix(longestMatch);
          } else {
            // No match found - set both to first allowed prefix
            setSelectedPrefix(normalizedPrefixes[0]);
            setCurrentBrowsePath(normalizedPrefixes[0]);
          }
        }
      } else if (isRestrictedMode) {
        // Initialize with first allowed prefix
        // UX Note: In restricted mode, the confirm button is enabled by default
        // because we pre-select the first allowed prefix as a sensible default.
        // Users can still change the prefix or navigate within it before confirming.
        setSelectedPrefix(normalizedPrefixes[0]);
        setCurrentBrowsePath(normalizedPrefixes[0]);
      } else {
        // Unrestricted mode - start at root
        setSelectedPrefix("");
        setCurrentBrowsePath("");
      }
      setValidationError("");
    }
  }, [open, normalizedPrefixes, isRestrictedMode, initialPath]);

  // Update current browse path when selected prefix changes
  useEffect(() => {
    if (isRestrictedMode && selectedPrefix && selectedPrefix !== currentBrowsePath) {
      setCurrentBrowsePath(selectedPrefix);
      setValidationError("");
    }
  }, [selectedPrefix, isRestrictedMode, currentBrowsePath]);

  // Validate path against allowed prefixes
  const validatePath = useCallback(
    (path: string): boolean => {
      if (!isRestrictedMode) {
        return true; // Unrestricted mode - all paths valid
      }

      // Normalize the candidate path by ensuring it ends with /
      const normalizedPath = path.endsWith("/") ? path : `${path}/`;

      // Check if path starts with any allowed prefix (only check forward, not reverse)
      return normalizedPrefixes.some((prefix) => normalizedPath.startsWith(prefix));
    },
    [isRestrictedMode, normalizedPrefixes]
  );

  // Handle prefix selection change
  const handlePrefixChange = useCallback((event: any) => {
    const newPrefix = event.target.value;
    setSelectedPrefix(newPrefix);
  }, []);

  // Handle path change from S3Explorer navigation
  const handlePathChange = useCallback((path: string) => {
    setCurrentBrowsePath(path);
    setValidationError("");
  }, []);

  // Compute the initial path for S3Explorer
  const s3ExplorerInitialPath = useMemo(() => {
    if (initialPath) {
      return initialPath;
    }
    if (isRestrictedMode && selectedPrefix) {
      return selectedPrefix;
    }
    return "";
  }, [initialPath, isRestrictedMode, selectedPrefix]);

  // Compute the restricted base path for S3Explorer
  const s3ExplorerRestrictedBase = useMemo(() => {
    if (!isRestrictedMode) {
      return undefined;
    }

    // Derive from the best matching prefix of currentBrowsePath
    const pathToCheck = currentBrowsePath || selectedPrefix;
    if (!pathToCheck) {
      return undefined;
    }

    // Ensure consistent normalization with trailing slash
    const normalizedPath = pathToCheck.endsWith("/") ? pathToCheck : `${pathToCheck}/`;

    // Find the longest matching prefix
    let longestMatch = "";
    for (const prefix of normalizedPrefixes) {
      if (normalizedPath.startsWith(prefix) && prefix.length > longestMatch.length) {
        longestMatch = prefix;
      }
    }

    // Always return with trailing slash for consistency
    const result = longestMatch || selectedPrefix || undefined;
    return result && !result.endsWith("/") ? `${result}/` : result;
  }, [isRestrictedMode, currentBrowsePath, selectedPrefix, normalizedPrefixes]);

  // Sync currentBrowsePath with restrictedBasePath changes only when genuinely needed
  useEffect(() => {
    if (isRestrictedMode && s3ExplorerRestrictedBase && open) {
      // Only update if currentBrowsePath is invalid or doesn't start with the restricted base
      if (currentBrowsePath && currentBrowsePath.startsWith(s3ExplorerRestrictedBase)) {
        return;
      }
      // Update only when the path is genuinely incorrect
      if (currentBrowsePath !== s3ExplorerRestrictedBase) {
        setCurrentBrowsePath(s3ExplorerRestrictedBase);
      }
    }
  }, [s3ExplorerRestrictedBase, isRestrictedMode, open, currentBrowsePath]);

  // Handle confirm button click
  const handleConfirm = useCallback(() => {
    if (!currentBrowsePath && currentBrowsePath !== "") {
      setValidationError(t("pathBrowser.validation.noPathSelected"));
      return;
    }

    if (validatePath(currentBrowsePath)) {
      // Normalize root path: convert '/' to '' for API consistency
      const normalizedPath = currentBrowsePath === "/" ? "" : currentBrowsePath;
      onPathSelect(normalizedPath);
      onClose();
    } else {
      setValidationError(t("pathBrowser.validation.invalidPath"));
    }
  }, [currentBrowsePath, validatePath, onPathSelect, onClose, t]);

  // Handle cancel button click
  const handleCancel = useCallback(() => {
    onClose();
  }, [onClose]);

  // Handle dialog close
  const handleDialogClose = useCallback(() => {
    onClose();
  }, [onClose]);

  // Display error if connector ID is invalid
  if (open && !connectorId) {
    return (
      <Dialog open={open} onClose={handleDialogClose} maxWidth="lg" fullWidth>
        <DialogTitle>{t("pathBrowser.title")}</DialogTitle>
        <DialogContent>
          <Alert severity="error" sx={{ mt: 2 }}>
            {t("pathBrowser.error.invalidConnector")}
          </Alert>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCancel}>{t("common.cancel")}</Button>
        </DialogActions>
      </Dialog>
    );
  }

  return (
    <Dialog open={open} onClose={handleDialogClose} maxWidth={isMobile ? "md" : "lg"} fullWidth>
      <DialogTitle>{t("pathBrowser.title")}</DialogTitle>

      <DialogContent>
        {/* Description Text */}
        <DialogContentText sx={{ mb: 2 }}>
          {isRestrictedMode
            ? t("pathBrowser.descriptionRestricted")
            : t("pathBrowser.descriptionUnrestricted")}
        </DialogContentText>

        {/* Prefix Selector - Only in restricted mode */}
        {isRestrictedMode && (
          <Box sx={{ mb: 3 }}>
            <FormControl fullWidth>
              <InputLabel id="prefix-select-label">{t("pathBrowser.prefixLabel")}</InputLabel>
              <Select
                labelId="prefix-select-label"
                id="prefix-select"
                value={selectedPrefix}
                label={t("pathBrowser.prefixLabel")}
                onChange={handlePrefixChange}
                sx={{
                  borderRadius: "8px",
                }}
              >
                {normalizedPrefixes.map((prefix) => (
                  <MenuItem key={prefix} value={prefix}>
                    {prefix.replace(/\/$/, "")}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Typography
              variant="caption"
              color="text.secondary"
              sx={{ display: "block", mt: 1, ml: 1.5 }}
            >
              {t("pathBrowser.prefixHelper")}
            </Typography>
          </Box>
        )}

        {/* Current Path Display */}
        <Paper
          elevation={0}
          sx={{
            p: 2,
            mb: 2,
            borderRadius: "8px",
            border: `1px solid ${alpha(theme.palette.divider, 0.2)}`,
            backgroundColor: alpha(theme.palette.primary.main, 0.02),
          }}
        >
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.5 }}>
            {t("pathBrowser.currentPath")}
          </Typography>
          <Typography
            variant="body1"
            sx={{
              fontWeight: 500,
              color: theme.palette.primary.main,
              fontFamily: "monospace",
              wordBreak: "break-all",
            }}
          >
            {currentBrowsePath || "/"}
          </Typography>
        </Paper>

        {/* Validation Error */}
        {validationError && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {validationError}
          </Alert>
        )}

        {/* Hint for user */}
        <Alert severity="info" sx={{ mb: 2 }}>
          {t("pathBrowser.hints.navigateAndConfirm")}
        </Alert>

        {/* S3Explorer Integration */}
        <Box
          sx={{
            border: `1px solid ${alpha(theme.palette.divider, 0.2)}`,
            borderRadius: "8px",
            overflow: "hidden",
            mb: 2,
          }}
        >
          <S3Explorer
            connectorId={connectorId}
            initialPath={s3ExplorerInitialPath}
            onPathChange={handlePathChange}
            restrictedBasePath={s3ExplorerRestrictedBase}
          />
        </Box>
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button
          onClick={handleCancel}
          sx={{
            textTransform: "none",
          }}
        >
          {t("common.cancel")}
        </Button>
        <Button
          variant="contained"
          color="primary"
          onClick={handleConfirm}
          disabled={!!validationError}
          sx={{
            textTransform: "none",
            borderRadius: "8px",
          }}
        >
          {t("pathBrowser.confirm")}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default PathBrowser;
