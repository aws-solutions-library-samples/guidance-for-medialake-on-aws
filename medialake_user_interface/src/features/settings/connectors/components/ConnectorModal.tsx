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
  Collapse,
} from "@mui/material";
import {
  Close as CloseIcon,
  CloudUpload as CloudUploadIcon,
  Info as InfoIcon,
  Refresh as RefreshIcon,
  ExpandMore as ExpandMoreIcon,
  ExpandLess as ExpandLessIcon,
  Add as AddIcon,
  Delete as DeleteIcon,
} from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import ApiStatusModal from "@/components/ApiStatusModal";
import { useApiMutationHandler } from "@/shared/hooks/useApiMutationHandler";
import {
  ConnectorResponse,
  CreateConnectorRequest,
} from "@/api/types/api.types";
import { useGetS3Buckets } from "@/api/hooks/useConnectors";
import { useGetAWSRegions } from "@/api/hooks/useAWSRegions";

interface ConnectorModalProps {
  open: boolean;
  onClose: () => void;
  editingConnector?: ConnectorResponse;
  onSave: (connectorData: CreateConnectorRequest) => Promise<void>;
  isCreating: boolean;
}

const CONNECTOR_TYPES = [
  {
    value: "s3",
    label: "Amazon S3",
    icon: CloudUploadIcon,
    colorHex: "#FF9900",
  },
  {
    value: "fsx",
    label: "Amazon FSx",
    icon: CloudUploadIcon,
    colorHex: "#FF9900",
  },
  { value: "empty", label: "", icon: CloudUploadIcon, colorHex: "#FF9900" },
];

const S3_BUCKET_TYPES = [
  {
    value: "existing",
    label: "Existing S3 Bucket",
    description: "Connect to an existing S3 bucket",
  },
  {
    value: "new",
    label: "New S3 Bucket",
    description: "Create a new S3 bucket",
  },
];

const S3_CONNECTOR_TYPES = [
  { value: "non-managed", label: "MediaLake Non-Managed" },
];

const S3_INTEGRATION_METHODS = [
  { value: "eventbridge" as const, label: "S3 EventBridge Notifications" },
  { value: "s3Notifications" as const, label: "S3 Event Notifications" },
] as const;

const AWS_REGIONS = [
  { value: "us-east-1", label: "US East (N. Virginia)" },
  { value: "us-east-2", label: "US East (Ohio)" },
  { value: "us-west-1", label: "US West (N. California)" },
  { value: "us-west-2", label: "US West (Oregon)" },
  { value: "af-south-1", label: "Africa (Cape Town)" },
  { value: "ap-east-1", label: "Asia Pacific (Hong Kong)" },
  { value: "ap-south-1", label: "Asia Pacific (Mumbai)" },
  { value: "ap-northeast-3", label: "Asia Pacific (Osaka)" },
  { value: "ap-northeast-2", label: "Asia Pacific (Seoul)" },
  { value: "ap-southeast-1", label: "Asia Pacific (Singapore)" },
  { value: "ap-southeast-2", label: "Asia Pacific (Sydney)" },
  { value: "ap-northeast-1", label: "Asia Pacific (Tokyo)" },
  { value: "ca-central-1", label: "Canada (Central)" },
  { value: "eu-central-1", label: "Europe (Frankfurt)" },
  { value: "eu-west-1", label: "Europe (Ireland)" },
  { value: "eu-west-2", label: "Europe (London)" },
  { value: "eu-south-1", label: "Europe (Milan)" },
  { value: "eu-west-3", label: "Europe (Paris)" },
  { value: "eu-north-1", label: "Europe (Stockholm)" },
  { value: "me-south-1", label: "Middle East (Bahrain)" },
  { value: "sa-east-1", label: "South America (São Paulo)" },
];

const ConnectorModal: React.FC<ConnectorModalProps> = ({
  open,
  onClose,
  editingConnector,
  onSave,
  isCreating,
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
  const [infoAnchorEl, setInfoAnchorEl] = useState<HTMLElement | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
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
      setType(editingConnector.type);
      setConfiguration(editingConnector.configuration || {});

      // Handle object prefixes from existing configuration
      if (editingConnector.objectPrefix) {
        // Check if objectPrefix exists at the top level
        if (typeof editingConnector.objectPrefix === "string") {
          // Convert legacy string format to array format
          setObjectPrefixes([editingConnector.objectPrefix]);
        } else if (Array.isArray(editingConnector.objectPrefix)) {
          // Use the array directly
          setObjectPrefixes(editingConnector.objectPrefix);
        } else {
          setObjectPrefixes([""]);
        }
      } else {
        setObjectPrefixes([""]);
      }

      setActiveStep(2);
      setBucketType("");
      setConfiguration({});
      setObjectPrefixes([""]);
      setActiveStep(0);
      setAwsRegion("");
      setBucketNameError("");
    } else {
      setName("");
      setType("");
      setBucketType("");
      setConfiguration({});
      setObjectPrefixes([""]);
      setActiveStep(0);
      setAwsRegion("");
      setBucketNameError("");
    }
  }, [editingConnector, open]);

  const handleNext = () => {
    setActiveStep((prev) => prev + 1);
  };

  const handleBack = () => {
    setActiveStep((prev) => prev - 1);
  };

  const handleAddPrefix = () => {
    setObjectPrefixes([...objectPrefixes, ""]);
  };

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

  const handleInfoClose = () => {
    setInfoAnchorEl(null);
  };

  // S3 Bucket Name Validation Logic
  const validateBucketName = (name: string): string => {
    if (!name) return "Bucket name is required.";
    if (name.length < 3 || name.length > 63) {
      return "Bucket name must be between 3 and 63 characters long.";
    }
    if (!/^[a-z0-9][a-z0-9.-]*[a-z0-9]$/.test(name)) {
      return "Bucket name can only contain lowercase letters, numbers, dots (.), and hyphens (-). Must start and end with a letter or number.";
    }
    if (name.includes("..") || name.includes(".-") || name.includes("-.")) {
      return "Bucket name cannot contain consecutive periods or periods adjacent to hyphens.";
    }
    if (/^(\d{1,3}\.){3}\d{1,3}$/.test(name)) {
      return "Bucket name cannot be formatted as an IP address.";
    }
    if (name.startsWith("xn--")) {
      return "Bucket name cannot start with 'xn--'.";
    }
    if (name.endsWith("-s3alias")) {
      return "Bucket name cannot end with '-s3alias'.";
    }
    return ""; // No error
  };

  const handleBucketNameChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const newName = event.target.value;
    setConfiguration({ ...configuration, bucket: newName });
    const errorMsg = validateBucketName(newName);
    setBucketNameError(errorMsg);
  };

  const handleSaveInternal = async () => {
    // Perform validation before attempting to save
    const bucketValidationError =
      bucketType === "new"
        ? validateBucketName(configuration.bucket || "")
        : "";
    if (bucketValidationError) {
      setBucketNameError(bucketValidationError);
      return; // Stop submission if bucket name is invalid
    }

    // Original validation logic with region requirement (commented out for restoration later)
    // if (!name || !type || (type === 's3' && (!s3ConnectorType || !configuration.integrationMethod || (bucketType === 'existing' && !configuration.bucket) || (bucketType === 'new' && (!configuration.bucket || !awsRegion))))) {
    //     alert('Please fill in all required fields, including Bucket Name and Region for new buckets.');
    //     return;
    // }

    // Modified validation logic - removed region requirement for new buckets
    if (
      !name ||
      !type ||
      (type === "s3" &&
        (!s3ConnectorType ||
          !configuration.integrationMethod ||
          (bucketType === "existing" && !configuration.bucket) ||
          (bucketType === "new" && !configuration.bucket)))
    ) {
      alert("Please fill in all required fields.");
      return;
    }

    // Filter out empty prefixes
    const filteredPrefixes = objectPrefixes.filter(
      (prefix) => prefix.trim() !== "",
    );

    const connectorData: CreateConnectorRequest = {
      name,
      type,
      description,
      configuration: {
        ...configuration,
        connectorType: s3ConnectorType,
        s3IntegrationMethod: configuration.integrationMethod as
          | "eventbridge"
          | "s3Notifications",
        objectPrefix: filteredPrefixes.length > 0 ? filteredPrefixes : [],
        ...(bucketType === "new" && {
          bucketType: "new",
          region: awsRegion,
        }),
        ...(bucketType === "existing" && {
          bucketType: "existing",
        }),
      },
    };

    await handleMutation(
      {
        mutation: {
          mutateAsync: onSave,
        } as any,
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
      connectorData,
    );
  };

  const renderS3BucketTypeSelection = () => (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {S3_BUCKET_TYPES.map((bucketType) => (
        <Box
          key={bucketType.value}
          onClick={() => {
            setBucketType(bucketType.value);
            handleNext();
          }}
          sx={{
            p: 3,
            border: `1px solid ${theme.palette.divider}`,
            borderRadius: "8px",
            cursor: "pointer",
            transition: "all 0.2s",
            "&:hover": {
              borderColor: theme.palette.primary.main,
              backgroundColor: `${theme.palette.primary.main}08`,
            },
          }}
        >
          <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
            {bucketType.label}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {bucketType.description}
          </Typography>
        </Box>
      ))}
    </Box>
  );

  const renderS3Configuration = () => (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {editingConnector ? (
        <>
          <TextField
            label="Connector Name"
            value={name}
            disabled
            fullWidth
            slotProps={{
              input: {
                sx: { bgcolor: "action.disabledBackground" },
              },
            }}
            helperText="Connector name cannot be modified after creation"
          />
          <Typography variant="caption" color="text.secondary" sx={{ mt: -1 }}>
            Amazon S3
          </Typography>
        </>
      ) : (
        <TextField
          label="Connector Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          fullWidth
          required
        />
      )}

      <TextField
        label="Description"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        fullWidth
        multiline
        rows={2}
      />

      {editingConnector ? (
        <>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <FormControl fullWidth disabled>
              <InputLabel>S3 Connector Type</InputLabel>
              <Select
                value={s3ConnectorType}
                label="S3 Connector Type"
                sx={{ bgcolor: "action.disabledBackground" }}
              >
                {S3_CONNECTOR_TYPES.map((type) => (
                  <MenuItem key={type.value} value={type.value}>
                    {type.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <IconButton onClick={handleInfoClick}>
              <InfoIcon />
            </IconButton>
          </Box>
          <FormControl fullWidth disabled>
            <InputLabel>S3 Integration Method</InputLabel>
            <Select
              value={configuration.integrationMethod || ""}
              label="S3 Integration Method"
              sx={{ bgcolor: "action.disabledBackground" }}
            >
              {S3_INTEGRATION_METHODS.map((method) => (
                <MenuItem key={method.value} value={method.value}>
                  {method.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <FormControl fullWidth disabled>
            <InputLabel>S3 Bucket</InputLabel>
            <Select
              value={configuration.bucket || ""}
              label="S3 Bucket"
              sx={{ bgcolor: "action.disabledBackground" }}
            >
              <MenuItem value={configuration.bucket}>
                {configuration.bucket}
              </MenuItem>
            </Select>
          </FormControl>
        </>
      ) : (
        <>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <FormControl fullWidth required>
              <InputLabel>S3 Connector Type</InputLabel>
              <Select
                value={s3ConnectorType}
                label="S3 Connector Type"
                onChange={(e) => setS3ConnectorType(e.target.value)}
              >
                {S3_CONNECTOR_TYPES.map((type) => (
                  <MenuItem key={type.value} value={type.value}>
                    {type.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <IconButton onClick={handleInfoClick}>
              <InfoIcon />
            </IconButton>
          </Box>
          <FormControl fullWidth required>
            <InputLabel>S3 Integration Method</InputLabel>
            <Select
              value={configuration.integrationMethod || ""}
              label="S3 Integration Method"
              onChange={(e) =>
                setConfiguration({
                  ...configuration,
                  integrationMethod: e.target.value,
                })
              }
            >
              {S3_INTEGRATION_METHODS.map((method) => (
                <MenuItem key={method.value} value={method.value}>
                  {method.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          {bucketType === "existing" && (
            <Box sx={{ display: "flex", alignItems: "flex-start", gap: 1 }}>
              <FormControl fullWidth required>
                <InputLabel>S3 Bucket</InputLabel>
                <Select
                  value={configuration.bucket || ""}
                  label="S3 Bucket"
                  onChange={(e) =>
                    setConfiguration({
                      ...configuration,
                      bucket: e.target.value,
                    })
                  }
                  disabled={isLoadingBuckets}
                  startAdornment={
                    isLoadingBuckets ? (
                      <CircularProgress size={20} sx={{ ml: 1 }} />
                    ) : null
                  }
                >
                  {buckets.map((bucket) => (
                    <MenuItem key={bucket} value={bucket}>
                      {bucket}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <IconButton
                onClick={() => refetchBuckets()}
                disabled={isLoadingBuckets}
                sx={{ mt: 1 }}
              >
                {isLoadingBuckets ? (
                  <CircularProgress size={24} />
                ) : (
                  <RefreshIcon />
                )}
              </IconButton>
            </Box>
          )}
          {bucketType === "new" && (
            <>
              <TextField
                label="New Bucket Name"
                value={configuration.bucket || ""}
                onChange={handleBucketNameChange}
                fullWidth
                required
                error={!!bucketNameError}
                helperText={
                  bucketNameError ||
                  "Bucket name must be globally unique, follow S3 naming rules."
                }
              />
              {/* AWS Region FormControl hidden as requested */}
              {/* <FormControl fullWidth required>
                                <InputLabel>AWS Region</InputLabel>
                                <Select
                                    value={awsRegion}
                                    label="AWS Region"
                                    onChange={(e) => setAwsRegion(e.target.value)}
                                >
                                    {AWS_REGIONS.map((region) => (
                                        <MenuItem key={region.value} value={region.value}>
                                            {region.label} ({region.value})
                                        </MenuItem>
                                    ))}
                                </Select>
                            </FormControl> */}
            </>
          )}
        </>
      )}

      <Button
        onClick={() => setShowAdvanced(!showAdvanced)}
        startIcon={showAdvanced ? <ExpandLessIcon /> : <ExpandMoreIcon />}
        sx={{ alignSelf: "flex-start", mt: 1 }}
      >
        Advanced configuration
      </Button>

      <Collapse in={showAdvanced}>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 2 }}>
          {objectPrefixes.map((prefix, index) => (
            <Box
              key={index}
              sx={{ display: "flex", alignItems: "center", gap: 1 }}
            >
              <TextField
                label={`Object Prefix ${objectPrefixes.length > 1 ? index + 1 : ""}`}
                value={prefix}
                onChange={(e) => handlePrefixChange(index, e.target.value)}
                fullWidth
                helperText="Optional prefix to filter objects (e.g., 'folder/')"
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
            Add Prefix
          </Button>
        </Box>
      </Collapse>
    </Box>
  );

  const steps = ["Select Type", "Select S3 Type", "Configuration"];

  const renderStepContent = (step: number) => {
    switch (step) {
      case 0:
        return (
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
                    // Disable FSx for now
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
                    border: `1px solid ${theme.palette.divider}`,
                    borderRadius: "8px",
                    // Disable FSx styling and interaction
                    cursor:
                      connectorType.value === "fsx" ? "not-allowed" : "pointer",
                    opacity: connectorType.value === "fsx" ? 0.5 : 1,
                    pointerEvents:
                      connectorType.value === "fsx" ? "none" : "auto",
                    transition: "all 0.2s",
                    "&:hover": {
                      borderColor: connectorType.colorHex,
                      backgroundColor: `${connectorType.colorHex}08`,
                    },
                  }}
                >
                  <Icon
                    sx={{ color: connectorType.colorHex, fontSize: 40, mb: 1 }}
                  />
                  <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                    {connectorType.label}
                  </Typography>
                </Box>
              );
            })}
          </Box>
        );
      case 1:
        return type === "s3" ? renderS3BucketTypeSelection() : null;
      case 2:
        return type === "s3" ? renderS3Configuration() : null;
      default:
        return null;
    }
  };

  return (
    <>
      <Dialog
        open={open}
        onClose={onClose}
        maxWidth="sm"
        fullWidth
        PaperProps={{
          sx: {
            borderRadius: "12px",
          },
        }}
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
            {editingConnector ? "Edit Connector" : "Add New Connector"}
          </Typography>
          <IconButton
            aria-label="close"
            onClick={onClose}
            sx={{
              color: theme.palette.grey[500],
              width: 40,
              height: 40,
            }}
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

          {renderStepContent(activeStep)}
        </DialogContent>

        <DialogActions sx={{ p: 2, gap: 1 }}>
          {!editingConnector && activeStep > 0 && (
            <Button
              onClick={handleBack}
              disabled={apiStatus.status === "loading"}
            >
              Back
            </Button>
          )}
          <Button
            onClick={onClose}
            color="inherit"
            disabled={apiStatus.status === "loading"}
          >
            Cancel
          </Button>
          {activeStep === steps.length - 1 || editingConnector ? (
            <Button
              variant="contained"
              onClick={handleSaveInternal}
              disabled={
                apiStatus.status === "loading" ||
                (bucketType === "new" && !!bucketNameError)
              }
              startIcon={
                apiStatus.status === "loading" ? (
                  <CircularProgress size={20} />
                ) : null
              }
              sx={{
                backgroundColor: theme.palette.primary.main,
                "&:hover": {
                  backgroundColor: theme.palette.primary.dark,
                },
              }}
            >
              {editingConnector ? "Save Changes" : "Add Connector"}
            </Button>
          ) : (
            <Button
              variant="contained"
              onClick={handleNext}
              disabled={
                !type ||
                (activeStep === 1 && !bucketType) ||
                apiStatus.status === "loading" ||
                (bucketType === "new" && !!bucketNameError)
              }
            >
              Next
            </Button>
          )}
        </DialogActions>

        <Popover
          open={Boolean(infoAnchorEl)}
          anchorEl={infoAnchorEl}
          onClose={handleInfoClose}
          anchorOrigin={{
            vertical: "bottom",
            horizontal: "center",
          }}
          transformOrigin={{
            vertical: "top",
            horizontal: "center",
          }}
        >
          <Box sx={{ p: 2, maxWidth: 400 }}>
            <Typography variant="body2" sx={{ mb: 2 }}>
              • MediaLake Non-Managed (If/when other remote storage systems are
              introduced this would be that category)
            </Typography>
            <Typography variant="body2" sx={{ mb: 2 }}>
              • Original files are kept on bucket, folder structure is not
              modified
            </Typography>
            <Typography variant="body2">
              • Representations of files created, such as proxies, will be put
              in a MediaLake managed bucket with a shadow folder structure
            </Typography>
          </Box>
        </Popover>
      </Dialog>

      {/* Render the ApiStatusModal only when not idle */}
      {apiStatus.status !== "idle" && (
        <ApiStatusModal
          open={apiStatus.show}
          // Status is now guaranteed not to be 'idle' here
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
