import React, { useState, useEffect } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Typography,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  Stepper,
  Step,
  StepLabel,
  IconButton,
  useTheme,
  Popover,
  CircularProgress,
  Checkbox,
  FormControlLabel,
  ToggleButtonGroup,
  ToggleButton,
  Autocomplete,
  Chip,
  Alert,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from "@mui/material";
import { alpha } from "@mui/material/styles";
import {
  Close as CloseIcon,
  CloudUpload as CloudUploadIcon,
  Info as InfoIcon,
  Refresh as RefreshIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
  ExpandMore as ExpandMoreIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import ApiStatusModal from "@/components/ApiStatusModal";
import { useApiMutationHandler } from "@/shared/hooks/useApiMutationHandler";
import { ConnectorResponse, CreateConnectorRequest } from "@/api/types/api.types";
import { useGetS3Buckets } from "@/api/hooks/useConnectors";
import { brandTokens } from "@/theme/tokens";

interface ConnectorModalProps {
  open: boolean;
  onClose: () => void;
  editingConnector?: ConnectorResponse;
  onSave: (connectorData: CreateConnectorRequest) => Promise<void>;
  isCreating: boolean;
}

/** AWS brand orange — used for S3/FSx connector icons and accents. */
const AWS_BRAND_ORANGE = brandTokens.aws.orange;

const CONNECTOR_TYPES = [
  {
    value: "s3",
    label: "Amazon S3",
    icon: CloudUploadIcon,
    colorHex: AWS_BRAND_ORANGE,
  },
  {
    value: "fsx",
    label: "Amazon FSx",
    icon: CloudUploadIcon,
    colorHex: AWS_BRAND_ORANGE,
  },
  { value: "empty", label: "", icon: CloudUploadIcon, colorHex: AWS_BRAND_ORANGE },
];

const getS3BucketTypes = (t: (key: string) => string) => [
  {
    value: "existing",
    label: "Existing S3 Bucket",
    description: t("common.messages.connectToExistingS3Bucket"),
  },
  {
    value: "new",
    label: "New S3 Bucket",
    description: t("common.messages.createNewS3Bucket"),
  },
];

const S3_CONNECTOR_TYPES = [{ value: "non-managed", label: "MediaLake Non-Managed" }];

const S3_INTEGRATION_METHODS = [
  { value: "eventbridge" as const, label: "S3 EventBridge Notifications" },
  { value: "s3Notifications" as const, label: "S3 Event Notifications" },
] as const;

/** The integration method we recommend operators choose. */
const RECOMMENDED_INTEGRATION_METHOD = "eventbridge";

/**
 * Supported file extensions grouped by media type, mirroring the backend
 * source of truth in `lambdas/common_libraries/file_extensions.py`. Ordered
 * Video → Audio → Image for display. These are suggestions only — the
 * Autocomplete is free-solo, so operators can add new or not-yet-listed
 * extensions, and the backend normalizes whatever is sent.
 */
const SUPPORTED_FILE_EXTENSIONS_BY_TYPE: { type: string; extensions: string[] }[] = [
  { type: "Video", extensions: ["flv", "mp4", "mov", "avi", "mkv", "webm", "mxf", "mts"] },
  { type: "Audio", extensions: ["wav", "aiff", "aif", "mp3", "pcm", "m4a"] },
  {
    type: "Image",
    extensions: [
      "apng",
      "avif",
      "bmp",
      "gif",
      "ico",
      "j2k",
      "jp2",
      "jpeg",
      "jpg",
      "pbm",
      "pcx",
      "pgm",
      "png",
      "ppm",
      "psd",
      "svg",
      "tif",
      "tiff",
      "webp",
      "wmf",
      "xbm",
      "xpm",
      "exr",
      "cr2",
      "erf",
      "nef",
    ],
  },
];

/** Flat, grouped option list for the file-extension Autocomplete. */
const SUPPORTED_FILE_EXTENSION_OPTIONS: { type: string; ext: string }[] =
  SUPPORTED_FILE_EXTENSIONS_BY_TYPE.flatMap(({ type, extensions }) =>
    extensions.map((ext) => ({ type, ext }))
  );

/** Normalize a free-typed extension: lowercase, trim, strip a leading dot. */
const normalizeExtension = (value: string): string =>
  value.trim().toLowerCase().replace(/^\.+/, "");

/**
 * Common MIME/content-type suggestions for the filter, grouped by media type.
 * Wildcards (e.g. "image/*") match any subtype. The Autocomplete is free-solo,
 * so operators can add exact types not listed here; the backend normalizes them.
 */
const MIME_TYPE_OPTIONS: { group: string; value: string }[] = [
  { group: "Wildcards", value: "video/*" },
  { group: "Wildcards", value: "audio/*" },
  { group: "Wildcards", value: "image/*" },
  { group: "Video", value: "video/mp4" },
  { group: "Video", value: "video/quicktime" },
  { group: "Video", value: "video/x-msvideo" },
  { group: "Video", value: "video/x-matroska" },
  { group: "Video", value: "video/webm" },
  { group: "Audio", value: "audio/wav" },
  { group: "Audio", value: "audio/mpeg" },
  { group: "Audio", value: "audio/mp4" },
  { group: "Audio", value: "audio/aiff" },
  { group: "Image", value: "image/jpeg" },
  { group: "Image", value: "image/png" },
  { group: "Image", value: "image/gif" },
  { group: "Image", value: "image/tiff" },
  { group: "Image", value: "image/webp" },
  { group: "Image", value: "image/svg+xml" },
];

/** Normalize a free-typed MIME pattern: lowercase, trim, drop parameters. */
const normalizeMimeType = (value: string): string =>
  value.trim().toLowerCase().split(";")[0].trim();

const ConnectorModal: React.FC<ConnectorModalProps> = ({
  open,
  onClose,
  editingConnector,
  onSave,
}) => {
  const theme = useTheme();
  const { t } = useTranslation();
  const { apiStatus, handleMutation, closeApiStatus } = useApiMutationHandler();
  const [activeStep, setActiveStep] = useState(0);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [type, setType] = useState("");
  const [bucketType, setBucketType] = useState("");
  const [s3ConnectorType, setS3ConnectorType] = useState("");
  const [configuration, setConfiguration] = useState<Record<string, any>>({});
  const [objectPrefixes, setObjectPrefixes] = useState<string[]>([""]);
  const [allowedFileExtensions, setAllowedFileExtensions] = useState<string[]>([]);
  const [fileFilterMimeTypes, setFileFilterMimeTypes] = useState<string[]>([]);
  const [fileFilterMode, setFileFilterMode] = useState<"allow" | "deny">("allow");
  const [infoAnchorEl, setInfoAnchorEl] = useState<HTMLElement | null>(null);
  const [allowUploads, setAllowUploads] = useState(false);
  const {
    data: s3BucketsResponse,
    isLoading: isLoadingBuckets,
    refetch: refetchBuckets,
  } = useGetS3Buckets();
  const buckets = s3BucketsResponse?.data?.buckets || [];
  const [awsRegion, setAwsRegion] = useState("");
  const [bucketNameError, setBucketNameError] = useState("");

  useEffect(() => {
    if (editingConnector) {
      setName(editingConnector.name);
      setDescription(editingConnector.description || "");
      setType(editingConnector.type);
      setConfiguration(editingConnector.configuration || {});
      const connectorType = editingConnector.configuration?.connectorType;
      setS3ConnectorType(typeof connectorType === "string" ? connectorType : "non-managed");

      // Normalize integration method from either field
      const method =
        editingConnector.integrationMethod || editingConnector.configuration?.s3IntegrationMethod;
      if (method) {
        setConfiguration((prev) => ({ ...prev, s3IntegrationMethod: method }));
      }

      // Handle object prefixes from existing configuration
      if (editingConnector.objectPrefix) {
        if (typeof editingConnector.objectPrefix === "string") {
          setObjectPrefixes([editingConnector.objectPrefix]);
        } else if (Array.isArray(editingConnector.objectPrefix)) {
          setObjectPrefixes(editingConnector.objectPrefix);
        } else {
          setObjectPrefixes([""]);
        }
      } else {
        setObjectPrefixes([""]);
      }

      setAllowUploads(
        editingConnector.allowUploads ?? editingConnector.configuration?.allowUploads ?? false
      );

      // Initialize the file filter from the existing connector config. Prefer
      // the structured `fileFilter`; fall back to the legacy
      // `allowedFileExtensions` allow-list. Absent on both => "allow all".
      const existingFilter =
        (editingConnector as any).fileFilter ?? editingConnector.configuration?.fileFilter;
      const legacyExtensions =
        (editingConnector as any).allowedFileExtensions ??
        editingConnector.configuration?.allowedFileExtensions;

      if (existingFilter && typeof existingFilter === "object") {
        setFileFilterMode(existingFilter.mode === "deny" ? "deny" : "allow");
        setAllowedFileExtensions(
          Array.isArray(existingFilter.extensions)
            ? existingFilter.extensions.map((ext: string) => normalizeExtension(String(ext)))
            : []
        );
        setFileFilterMimeTypes(
          Array.isArray(existingFilter.mimeTypes)
            ? existingFilter.mimeTypes.map((mime: string) => normalizeMimeType(String(mime)))
            : []
        );
      } else {
        setFileFilterMode("allow");
        setAllowedFileExtensions(
          Array.isArray(legacyExtensions)
            ? legacyExtensions.map((ext: string) => normalizeExtension(String(ext)))
            : []
        );
        setFileFilterMimeTypes([]);
      }

      // Edit mode uses a single condensed screen, not the wizard.
      setActiveStep(0);
    } else {
      setName("");
      setDescription("");
      setType("");
      setBucketType("");
      setS3ConnectorType("non-managed");
      setConfiguration({ s3IntegrationMethod: "eventbridge" });
      setObjectPrefixes([""]);
      setAllowedFileExtensions([]);
      setFileFilterMimeTypes([]);
      setFileFilterMode("allow");
      setActiveStep(0);
      setAwsRegion("");
      setBucketNameError("");
      setAllowUploads(false);
    }
  }, [editingConnector, open]);

  const handleNext = () => setActiveStep((prev) => prev + 1);
  const handleBack = () => setActiveStep((prev) => prev - 1);

  const handleAddPrefix = () => setObjectPrefixes([...objectPrefixes, ""]);

  const handleRemovePrefix = (index: number) => {
    const newPrefixes = [...objectPrefixes];
    newPrefixes.splice(index, 1);
    if (newPrefixes.length === 0) {
      newPrefixes.push(""); // Always keep at least one field
    }
    setObjectPrefixes(newPrefixes);
  };

  const handlePrefixChange = (index: number, value: string) => {
    const newPrefixes = [...objectPrefixes];
    newPrefixes[index] = value;
    setObjectPrefixes(newPrefixes);
  };

  const handleInfoClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setInfoAnchorEl(event.currentTarget);
  };

  const handleInfoClose = () => setInfoAnchorEl(null);

  // S3 Bucket Name Validation Logic
  const validateBucketName = (value: string): string => {
    if (!value) return "Bucket name is required.";
    if (value.length < 3 || value.length > 63) {
      return "Bucket name must be between 3 and 63 characters long.";
    }
    if (!/^[a-z0-9][a-z0-9.-]*[a-z0-9]$/.test(value)) {
      return "Bucket name can only contain lowercase letters, numbers, dots (.), and hyphens (-). Must start and end with a letter or number.";
    }
    if (value.includes("..") || value.includes(".-") || value.includes("-.")) {
      return "Bucket name cannot contain consecutive periods or periods adjacent to hyphens.";
    }
    if (/^(\d{1,3}\.){3}\d{1,3}$/.test(value)) {
      return "Bucket name cannot be formatted as an IP address.";
    }
    if (value.startsWith("xn--")) {
      return "Bucket name cannot start with 'xn--'.";
    }
    if (value.endsWith("-s3alias")) {
      return "Bucket name cannot end with '-s3alias'.";
    }
    return ""; // No error
  };

  const handleBucketNameChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const newName = event.target.value;
    setConfiguration({ ...configuration, bucket: newName });
    setBucketNameError(validateBucketName(newName));
  };

  const buildConnectorData = (): CreateConnectorRequest => {
    const filteredPrefixes = objectPrefixes.filter((prefix) => prefix.trim() !== "");

    const normalizedExtensions = Array.from(
      new Set(
        allowedFileExtensions.map((ext) => normalizeExtension(ext)).filter((ext) => ext !== "")
      )
    );
    const normalizedMimeTypes = Array.from(
      new Set(
        fileFilterMimeTypes.map((mime) => normalizeMimeType(mime)).filter((mime) => mime !== "")
      )
    );
    // Build the canonical structured filter. Omitted when nothing is configured
    // so the backend treats it as "allow all" (backwards compatible).
    const fileFilter =
      normalizedExtensions.length > 0 || normalizedMimeTypes.length > 0
        ? {
            mode: fileFilterMode,
            extensions: normalizedExtensions,
            mimeTypes: normalizedMimeTypes,
          }
        : undefined;

    const { integrationMethod, ...restConfig } = configuration as any;
    const newBucketExtras = bucketType === "new" && awsRegion.trim() ? { region: awsRegion } : {};

    return {
      name,
      type,
      description,
      configuration: {
        ...restConfig,
        connectorType: s3ConnectorType,
        s3IntegrationMethod: (configuration.s3IntegrationMethod || integrationMethod) as
          | "eventbridge"
          | "s3Notifications",
        objectPrefix: filteredPrefixes.length > 0 ? filteredPrefixes : [],
        allowedFileExtensions:
          fileFilter && fileFilter.mode === "allow" ? normalizedExtensions : [],
        fileFilter,
        allowUploads: allowUploads,
        bucketType: bucketType as "new" | "existing",
        ...newBucketExtras,
      },
    };
  };

  const handleSaveInternal = async () => {
    // For new connectors, validate the new bucket name before submitting.
    if (!editingConnector) {
      const bucketValidationError =
        bucketType === "new" ? validateBucketName(configuration.bucket || "") : "";
      if (bucketValidationError) {
        setBucketNameError(bucketValidationError);
        return;
      }

      if (
        !name ||
        !type ||
        (type === "s3" &&
          (!s3ConnectorType || !configuration.s3IntegrationMethod || !configuration.bucket))
      ) {
        alert("Please fill in all required fields.");
        return;
      }
    } else if (!name) {
      alert("Connector name is required.");
      return;
    }

    const connectorData = buildConnectorData();

    await handleMutation(
      {
        mutation: { mutateAsync: onSave } as any,
        actionMessages: {
          loading: editingConnector
            ? t("connectors.apiMessages.updating.loading")
            : t("connectors.apiMessages.creating.loading"),
          success: editingConnector
            ? t("connectors.apiMessages.updating.success")
            : t("connectors.apiMessages.creating.success"),
          error: editingConnector
            ? t("connectors.apiMessages.updating.error")
            : t("connectors.apiMessages.creating.error"),
        },
        onSuccess: () => {
          onClose();
        },
      },
      connectorData
    );
  };

  // ---- Step renderers -------------------------------------------------------

  const renderConnectorTypeSelection = () => (
    <Box
      sx={{
        display: "grid",
        gridTemplateColumns: "repeat(2, 1fr)",
        gap: 2,
      }}
    >
      {CONNECTOR_TYPES.map((connectorType) => {
        const Icon = connectorType.icon;
        return connectorType.value === "empty" ? (
          <Box key="empty" sx={{ visibility: "hidden" }} />
        ) : (
          <Box
            key={connectorType.value}
            onClick={() => {
              if (connectorType.value !== "fsx") {
                setType(connectorType.value);
                handleNext();
              }
            }}
            sx={{
              height: "120px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              alignItems: "center",
              border: `1px solid ${
                type === connectorType.value ? connectorType.colorHex : theme.palette.divider
              }`,
              borderRadius: "8px",
              cursor: connectorType.value === "fsx" ? "not-allowed" : "pointer",
              opacity: connectorType.value === "fsx" ? 0.5 : 1,
              pointerEvents: connectorType.value === "fsx" ? "none" : "auto",
              transition: "border-color 0.2s, background-color 0.2s",
              "&:hover": {
                borderColor: connectorType.colorHex,
                backgroundColor: alpha(connectorType.colorHex, 0.03),
              },
            }}
          >
            <Icon sx={{ color: connectorType.colorHex, fontSize: 40, mb: 1 }} />
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
              {connectorType.label}
            </Typography>
          </Box>
        );
      })}
    </Box>
  );

  const renderDetails = () => (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <TextField
        label={t("connectors.form.connectorName")}
        value={name}
        onChange={(e) => setName(e.target.value)}
        fullWidth
        required
      />
      <TextField
        label={t("connectors.form.description")}
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        fullWidth
        multiline
        rows={2}
      />
    </Box>
  );

  const renderStorage = () => (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {getS3BucketTypes(t).map((bt) => (
        <Box
          key={bt.value}
          onClick={() => {
            setBucketType(bt.value);
            // Clear any previously chosen bucket when switching types.
            setConfiguration((prev) => ({ ...prev, bucket: "" }));
            setBucketNameError("");
          }}
          sx={{
            p: 2.5,
            border: `1px solid ${
              bucketType === bt.value ? theme.palette.primary.main : theme.palette.divider
            }`,
            borderRadius: "8px",
            cursor: "pointer",
            backgroundColor:
              bucketType === bt.value ? alpha(theme.palette.primary.main, 0.04) : "transparent",
            transition: "border-color 0.2s, background-color 0.2s",
            "&:hover": {
              borderColor: theme.palette.primary.main,
              backgroundColor: alpha(theme.palette.primary.main, 0.03),
            },
          }}
        >
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 0.5 }}>
            {bt.label}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {bt.description}
          </Typography>
        </Box>
      ))}

      {bucketType === "existing" && (
        <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1, mt: 1 }}>
          <FormControl fullWidth required>
            <InputLabel>{t("connectors.form.s3Bucket")}</InputLabel>
            <Select
              value={configuration.bucket || ""}
              label={t("connectors.form.s3Bucket")}
              onChange={(e) => setConfiguration({ ...configuration, bucket: e.target.value })}
              disabled={isLoadingBuckets}
              startAdornment={
                isLoadingBuckets ? <CircularProgress size={20} sx={{ ml: 1 }} /> : null
              }
            >
              {buckets.map((bucket) => (
                <MenuItem key={bucket} value={bucket}>
                  {bucket}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <IconButton onClick={() => refetchBuckets()} disabled={isLoadingBuckets} sx={{ mt: 1 }}>
            {isLoadingBuckets ? <CircularProgress size={24} /> : <RefreshIcon />}
          </IconButton>
        </Box>
      )}

      {bucketType === "new" && (
        <TextField
          label={t("connectors.form.newBucketName")}
          value={configuration.bucket || ""}
          onChange={handleBucketNameChange}
          fullWidth
          required
          error={!!bucketNameError}
          helperText={bucketNameError || t("connectors.form.bucketNameHelper")}
          sx={{ mt: 1 }}
        />
      )}

      {bucketType && (
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 1 }}>
          <Typography variant="subtitle2">
            {t("connectors.form.objectPrefixesTitle", "Object Prefixes")}
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ mt: -1 }}>
            {t(
              "connectors.form.objectPrefixesHelper",
              "Restrict this connector to objects under one or more key prefixes. Leave empty to watch the whole bucket."
            )}
          </Typography>

          {objectPrefixes.map((prefix, index) => (
            <Box key={index} sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <TextField
                label={
                  objectPrefixes.length > 1
                    ? t("connectors.form.objectPrefixNumbered", { number: index + 1 })
                    : t("connectors.form.objectPrefix")
                }
                value={prefix}
                onChange={(e) => handlePrefixChange(index, e.target.value)}
                fullWidth
                helperText={t("connectors.form.pathHelper")}
              />
              <IconButton
                onClick={() => handleRemovePrefix(index)}
                sx={{ mt: index === 0 && objectPrefixes.length === 1 ? -3 : 0 }}
              >
                <DeleteIcon />
              </IconButton>
            </Box>
          ))}
          <Button
            startIcon={<AddIcon />}
            onClick={handleAddPrefix}
            sx={{ alignSelf: "flex-start", mt: 1 }}
          >
            {t("connectors.form.addPrefix", "Add Prefix")}
          </Button>
        </Box>
      )}
    </Box>
  );

  const renderAssetFilters = () => (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <Alert severity="info">
        {t(
          "connectors.form.indexingDefaultsNote",
          "Supported image, video, and audio formats are fully processed by the default pipelines. Any other file types you choose to ingest are stored as searchable, preview-only items with a file-type badge, without default-pipeline processing. Expand the section below to view the full list of supported formats."
        )}
      </Alert>

      <Accordion
        disableGutters
        elevation={0}
        sx={{
          border: `1px solid ${theme.palette.divider}`,
          borderRadius: 1,
          "&:before": { display: "none" },
        }}
      >
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          <Typography variant="subtitle2">
            {t("connectors.form.supportedFormatsTitle", "Supported formats")}
          </Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
            {SUPPORTED_FILE_EXTENSIONS_BY_TYPE.map(({ type, extensions }) => (
              <Box key={type}>
                <Typography variant="caption" sx={{ fontWeight: 600 }}>
                  {type}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {extensions.join(", ")}
                </Typography>
              </Box>
            ))}
          </Box>
        </AccordionDetails>
      </Accordion>

      <Typography variant="subtitle2" sx={{ mt: 1 }}>
        {t("connectors.form.fileFilter", "File Type Filtering")}
      </Typography>

      <ToggleButtonGroup
        exclusive
        size="small"
        value={fileFilterMode}
        onChange={(_event, newMode) => {
          if (newMode === "allow" || newMode === "deny") {
            setFileFilterMode(newMode);
          }
        }}
      >
        <ToggleButton value="allow">
          {t("connectors.form.fileFilterAllow", "Allow list")}
        </ToggleButton>
        <ToggleButton value="deny">{t("connectors.form.fileFilterDeny", "Deny list")}</ToggleButton>
      </ToggleButtonGroup>
      <Typography variant="caption" color="text.secondary" sx={{ mt: -1 }}>
        {fileFilterMode === "deny"
          ? t(
              "connectors.form.fileFilterDenyHelper",
              "Ingests all supported media except files that match the extensions or MIME types you list. Non-media file types are never ingested in deny mode."
            )
          : t(
              "connectors.form.fileFilterAllowHelper",
              "Ingests only files that match the extensions or MIME types you list — this replaces the default set rather than adding to it. List a non-media type (for example, pdf) to ingest it as a preview-only item. Leave both lists empty to ingest all supported media."
            )}
      </Typography>

      <Box>
        <Typography variant="subtitle2">
          {t("connectors.form.fileFilterExtensions", "File Extensions")}
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
          {t("connectors.form.fileFilterExtensionsExamples", "For example: mp4, mov, jpg")}
        </Typography>
        <Autocomplete
          multiple
          freeSolo
          options={SUPPORTED_FILE_EXTENSION_OPTIONS}
          groupBy={(option) => (typeof option === "string" ? "Custom" : option.type)}
          getOptionLabel={(option) => (typeof option === "string" ? option : option.ext)}
          value={allowedFileExtensions}
          onChange={(_event, newValue) => {
            const next = newValue.map((item) =>
              normalizeExtension(typeof item === "string" ? item : item.ext)
            );
            setAllowedFileExtensions(Array.from(new Set(next.filter((ext) => ext !== ""))));
          }}
          renderTags={(value, getTagProps) =>
            value.map((option, index) => {
              const label = typeof option === "string" ? option : option.ext;
              return (
                <Chip
                  variant="outlined"
                  label={label}
                  size="small"
                  {...getTagProps({ index })}
                  key={label}
                />
              );
            })
          }
          renderInput={(params) => (
            <TextField
              {...params}
              placeholder={t("connectors.form.fileFilterExtensionsPlaceholder", "Add an extension")}
            />
          )}
        />
      </Box>

      <Box>
        <Typography variant="subtitle2">
          {t("connectors.form.fileFilterMimeTypes", "MIME Types")}
        </Typography>
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
          {t(
            "connectors.form.fileFilterMimeTypesExamples",
            "For example: video/mp4 or image/* (a wildcard matches any subtype)"
          )}
        </Typography>
        <Autocomplete
          multiple
          freeSolo
          options={MIME_TYPE_OPTIONS}
          groupBy={(option) => (typeof option === "string" ? "Custom" : option.group)}
          getOptionLabel={(option) => (typeof option === "string" ? option : option.value)}
          value={fileFilterMimeTypes}
          onChange={(_event, newValue) => {
            const next = newValue.map((item) =>
              normalizeMimeType(typeof item === "string" ? item : item.value)
            );
            setFileFilterMimeTypes(Array.from(new Set(next.filter((mime) => mime !== ""))));
          }}
          renderTags={(value, getTagProps) =>
            value.map((option, index) => {
              const label = typeof option === "string" ? option : option.value;
              return (
                <Chip
                  variant="outlined"
                  label={label}
                  size="small"
                  {...getTagProps({ index })}
                  key={label}
                />
              );
            })
          }
          renderInput={(params) => (
            <TextField
              {...params}
              placeholder={t("connectors.form.fileFilterMimeTypesPlaceholder", "Add a MIME type")}
            />
          )}
        />
      </Box>
    </Box>
  );

  const renderAdvanced = () => (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {/* Uploads */}
      <Box>
        <FormControlLabel
          control={
            <Checkbox checked={allowUploads} onChange={(e) => setAllowUploads(e.target.checked)} />
          }
          label={t("connectors.form.allowUploads")}
        />
        <Typography variant="caption" color="text.secondary" sx={{ display: "block", ml: 4 }}>
          {t(
            "connectors.form.allowUploadsHelper",
            "Enable direct browser uploads to this S3 bucket. This adds a CORS rule to the bucket allowing GET, HEAD, PUT, and POST requests from the MediaLake application origin (standard and x-amz-* headers, ETag exposed, 1-hour preflight cache)."
          )}
        </Typography>
      </Box>

      {/* S3 Integration Method */}
      <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
        <FormControl fullWidth required>
          <InputLabel>{t("connectors.form.s3IntegrationMethod")}</InputLabel>
          <Select
            value={configuration.s3IntegrationMethod || ""}
            label={t("connectors.form.s3IntegrationMethod")}
            onChange={(e) =>
              setConfiguration({ ...configuration, s3IntegrationMethod: e.target.value })
            }
          >
            {S3_INTEGRATION_METHODS.map((method) => (
              <MenuItem key={method.value} value={method.value}>
                {method.label}
                {method.value === RECOMMENDED_INTEGRATION_METHOD
                  ? ` ${t("connectors.form.recommendedSuffix", "(Recommended)")}`
                  : ""}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <IconButton onClick={handleInfoClick}>
          <InfoIcon />
        </IconButton>
      </Box>
      <Alert
        severity={
          configuration.s3IntegrationMethod &&
          configuration.s3IntegrationMethod !== RECOMMENDED_INTEGRATION_METHOD
            ? "warning"
            : "info"
        }
      >
        {t(
          "connectors.form.integrationMethodNote",
          "S3 EventBridge Notifications is the recommended integration method, providing reliable and scalable event delivery. S3 Event Notifications remains available but offers fewer delivery guarantees for high-volume buckets."
        )}
      </Alert>

      {/* S3 Connector Type */}
      <FormControl fullWidth required>
        <InputLabel>{t("connectors.form.s3ConnectorType")}</InputLabel>
        <Select
          value={s3ConnectorType}
          label={t("connectors.form.s3ConnectorType")}
          onChange={(e) => setS3ConnectorType(e.target.value)}
        >
          {S3_CONNECTOR_TYPES.map((ct) => (
            <MenuItem key={ct.value} value={ct.value}>
              {ct.label}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
    </Box>
  );

  const renderEditScreen = () => (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <Alert severity="info">
        {t(
          "connectors.form.editNote",
          "Only the connector name and description can be changed after creation. Storage, asset filters, and advanced settings are fixed."
        )}
      </Alert>

      <TextField
        label={t("connectors.form.connectorName")}
        value={name}
        onChange={(e) => setName(e.target.value)}
        fullWidth
        required
      />
      <TextField
        label={t("connectors.form.description")}
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        fullWidth
        multiline
        rows={2}
      />

      <FormControl fullWidth disabled>
        <InputLabel>{t("connectors.form.s3Bucket")}</InputLabel>
        <Select
          value={configuration.bucket || ""}
          label={t("connectors.form.s3Bucket")}
          sx={{ bgcolor: "action.disabledBackground" }}
        >
          <MenuItem value={configuration.bucket}>{configuration.bucket}</MenuItem>
        </Select>
      </FormControl>

      <TextField
        label={t("connectors.form.s3IntegrationMethod")}
        value={
          S3_INTEGRATION_METHODS.find((m) => m.value === configuration.s3IntegrationMethod)
            ?.label ||
          configuration.s3IntegrationMethod ||
          ""
        }
        fullWidth
        disabled
        slotProps={{ input: { sx: { bgcolor: "action.disabledBackground" } } }}
      />
    </Box>
  );

  const steps = [
    t("connectors.steps.type", "Connector Type"),
    t("connectors.steps.details", "Details"),
    t("connectors.steps.storage", "Storage"),
    t("connectors.steps.indexing", "Asset Filters"),
    t("connectors.steps.advanced", "Advanced"),
  ];

  const renderStepContent = (step: number) => {
    switch (step) {
      case 0:
        return renderConnectorTypeSelection();
      case 1:
        return type === "s3" ? renderDetails() : null;
      case 2:
        return type === "s3" ? renderStorage() : null;
      case 3:
        return type === "s3" ? renderAssetFilters() : null;
      case 4:
        return type === "s3" ? renderAdvanced() : null;
      default:
        return null;
    }
  };

  // Whether the user can advance from the current step.
  const isNextDisabled = (): boolean => {
    if (apiStatus.status === "loading") return true;
    switch (activeStep) {
      case 0:
        return !type;
      case 1:
        return !name.trim();
      case 2:
        if (!bucketType) return true;
        if (!configuration.bucket) return true;
        if (bucketType === "new" && !!bucketNameError) return true;
        return false;
      default:
        return false;
    }
  };

  const isLastStep = activeStep === steps.length - 1;

  return (
    <>
      <Dialog
        open={open}
        onClose={onClose}
        maxWidth="sm"
        fullWidth
        disableEnforceFocus={apiStatus.status !== "idle"}
      >
        <DialogTitle
          sx={{
            m: 0,
            p: 2,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <Typography variant="h6">
            {editingConnector
              ? t("pipelines.editConnector", "Edit Connector")
              : t("pipelines.addConnector", "Add New Connector")}
          </Typography>
          <IconButton
            aria-label="close"
            onClick={onClose}
            sx={{ color: theme.palette.grey[500], width: 40, height: 40 }}
          >
            <CloseIcon />
          </IconButton>
        </DialogTitle>

        <DialogContent dividers>
          {!editingConnector && (
            <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
              {steps.map((label) => (
                <Step key={label}>
                  <StepLabel>{label}</StepLabel>
                </Step>
              ))}
            </Stepper>
          )}

          {editingConnector ? renderEditScreen() : renderStepContent(activeStep)}
        </DialogContent>

        <DialogActions sx={{ p: 2, gap: 1 }}>
          {!editingConnector && activeStep > 0 && (
            <Button onClick={handleBack} disabled={apiStatus.status === "loading"}>
              {t("common.actions.back", "Back")}
            </Button>
          )}
          <Button onClick={onClose} color="inherit" disabled={apiStatus.status === "loading"}>
            {t("common.actions.cancel")}
          </Button>
          {isLastStep || editingConnector ? (
            <Button
              variant="contained"
              onClick={handleSaveInternal}
              disabled={
                apiStatus.status === "loading" ||
                (editingConnector ? !name.trim() : bucketType === "new" && !!bucketNameError)
              }
              startIcon={apiStatus.status === "loading" ? <CircularProgress size={20} /> : null}
              sx={{
                backgroundColor: theme.palette.primary.main,
                "&:hover": { backgroundColor: theme.palette.primary.dark },
              }}
            >
              {editingConnector
                ? t("pipelines.saveChanges", "Save Changes")
                : t("pipelines.addConnector", "Add Connector")}
            </Button>
          ) : (
            <Button variant="contained" onClick={handleNext} disabled={isNextDisabled()}>
              {t("common.actions.next", "Next")}
            </Button>
          )}
        </DialogActions>

        <Popover
          open={Boolean(infoAnchorEl)}
          anchorEl={infoAnchorEl}
          onClose={handleInfoClose}
          anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
          transformOrigin={{ vertical: "top", horizontal: "center" }}
        >
          <Box sx={{ p: 2, maxWidth: 400 }}>
            <Typography variant="body2" sx={{ mb: 2 }}>
              • MediaLake Non-Managed (If/when other remote storage systems are introduced this
              would be that category)
            </Typography>
            <Typography variant="body2" sx={{ mb: 2 }}>
              • Original files are kept on bucket, folder structure is not modified
            </Typography>
            <Typography variant="body2">
              • Representations of files created, such as proxies, will be put in a MediaLake
              managed bucket with a shadow folder structure
            </Typography>
          </Box>
        </Popover>
      </Dialog>

      {apiStatus.status !== "idle" && (
        <ApiStatusModal
          open={apiStatus.show}
          status={apiStatus.status}
          action={apiStatus.action}
          message={apiStatus.message}
          onClose={closeApiStatus}
        />
      )}
    </>
  );
};

export default ConnectorModal;
