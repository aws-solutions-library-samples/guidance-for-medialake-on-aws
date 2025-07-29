import React from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  Box,
  Typography,
  Stepper,
  Step,
  StepLabel,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Avatar,
  Button,
  TextField,
  InputAdornment,
} from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import { useTranslation } from "react-i18next";
import { Form } from "@/forms/components/Form";
import { FormField } from "@/forms/components/FormField";
import { FormSelect } from "@/forms/components/FormSelect";
import { useFormWithValidation } from "@/forms/hooks/useFormWithValidation";
import {
  IntegrationFormProps,
  IntegrationFormData,
  IntegrationFormResult,
} from "./types";
import {
  integrationFormSchema,
  createIntegrationFormDefaults,
} from "./schemas/integrationFormSchema";
import {
  useCreateIntegration,
  useUpdateIntegration,
} from "@/features/settings/integrations/api/integrations.controller";
import { IntegrationsNodesService } from "@/features/settings/integrations/services/integrations-nodes.service";
import { IntegrationNode } from "@/features/settings/integrations/types";
import { IntegrationConfiguration } from "./components/IntegrationConfiguration";

const createSteps = [
  "integrations.selectIntegration",
  "integrations.configureIntegration",
];
const editSteps = ["integrations.configureIntegration"];

export const IntegrationForm: React.FC<IntegrationFormProps> = ({
  open,
  onClose,
  filteredNodes,
  onSubmitSuccess,
  onSubmit,
  editingIntegration,
}) => {
  const { t } = useTranslation();
  const [activeStep, setActiveStep] = React.useState(0);
  const [selectedNodeId, setSelectedNodeId] = React.useState<string>("");
  const [searchTerm, setSearchTerm] = React.useState("");
  const createIntegration = useCreateIntegration();
  const updateIntegration = useUpdateIntegration();

  // Determine if we're in edit mode
  const isEditMode = !!editingIntegration;

  // Use filteredNodes if provided, otherwise fetch all nodes
  const { nodes: fetchedNodes = [], isLoading: isLoadingNodes } =
    IntegrationsNodesService.useNodes();
  const rawNodes = filteredNodes || fetchedNodes;

  const defaultFormValues: IntegrationFormData = React.useMemo(() => {
    if (isEditMode && editingIntegration) {
      // Extract auth data from configuration if available
      const config = editingIntegration.configuration || {};
      const authType = config.auth?.type || "apiKey";
      const credentials = config.auth?.credentials || {};

      // Try to construct nodeId from the integration type
      // The nodeId should be in format like "node-twelve-labs-api"
      const nodeId =
        config.nodeId ||
        `node-${editingIntegration.type}-api` ||
        editingIntegration.type ||
        "";

      console.log("[IntegrationForm] Edit mode - extracting data:", {
        editingIntegration,
        config,
        authType,
        credentials,
        constructedNodeId: nodeId,
      });

      return {
        nodeId: nodeId,
        description: editingIntegration.description || config.description || "",
        auth: {
          type: authType,
          credentials: {
            apiKey: credentials.apiKey || "***existing***", // Placeholder for existing API key
            iamRole: credentials.iamRole || "",
          },
        },
      };
    }

    return {
      nodeId: "",
      description: "",
      auth: {
        type: "apiKey",
        credentials: {},
      },
    };
  }, [isEditMode, editingIntegration]);

  const form = useFormWithValidation<IntegrationFormData>({
    defaultValues: defaultFormValues,
    validationSchema: integrationFormSchema,
    mode: "onChange",
  });

  // Process nodes only when rawNodes changes
  const nodes: IntegrationNode[] = React.useMemo(() => {
    if (!rawNodes.length) return [];
    return rawNodes.map((node) => {
      const authMethod = node.auth?.authMethod;
      return {
        nodeId:
          node.nodeId ||
          `node-${node.info.title.toLowerCase().replace(/\s+/g, "-")}`,
        info: {
          title: node.info.title,
          description: node.info.description,
        },
        auth:
          authMethod === "awsIam" || authMethod === "apiKey"
            ? { authMethod: authMethod as "awsIam" | "apiKey" }
            : { authMethod: "apiKey" as const },
      };
    });
  }, [rawNodes]);

  // Memoize form values to prevent infinite render loops but still update when needed
  const formValues = React.useMemo(
    () => form.getValues(),
    [
      // Only update when these specific form values change
      form.watch("nodeId"),
      form.watch("description"),
      form.watch("auth.type"),
      form.watch("auth.credentials.apiKey"),
      form.watch("auth.credentials.iamRole"),
    ],
  );

  const handleSubmit = React.useCallback(
    async (data: IntegrationFormData) => {
      try {
        // If onSubmit prop is provided, use it (new approach)
        if (onSubmit) {
          console.log("Using new onSubmit approach with data:", data);
          await onSubmit(data);
          return;
        }

        // Otherwise, fall back to old approach for backward compatibility
        console.log("Using legacy onSubmitSuccess approach with data:", data);

        // Close the form immediately when the user clicks the button
        onClose();

        let result;

        if (isEditMode && editingIntegration) {
          console.log("Starting integration update with data:", data);
          result = await updateIntegration.mutateAsync({
            id: editingIntegration.id,
            data,
          });
          console.log("Integration updated successfully:", result);
        } else {
          console.log("Starting integration creation with data:", data);
          result = await createIntegration.mutateAsync(data);
          console.log("Integration created successfully:", result);
        }

        // Notify parent component of successful submission if callback exists
        if (onSubmitSuccess) {
          console.log("Calling onSubmitSuccess with result:", result);
          // Convert the result to match IntegrationFormResult type
          // The result might be a single Integration object or an IntegrationsResponse
          const formResult: IntegrationFormResult = {
            // Try to get the id from various possible locations in the result
            id:
              (result as any).id ||
              (result.data && result.data[0] && result.data[0].id) ||
              editingIntegration?.id ||
              data.nodeId, // Fallback to nodeId if no id is found
            nodeId: data.nodeId,
            // Add any additional properties needed by the parent component
            type: data.nodeId.replace("node-", "").replace("-api", ""),
            description: data.description,
          };
          console.log("Created form result for callback:", formResult);

          // Call onSubmitSuccess after API call completes
          onSubmitSuccess(formResult);
        }

        return result;
      } catch (error) {
        console.error(
          `Failed to ${isEditMode ? "update" : "create"} integration:`,
          {
            error,
            formData: data,
            selectedNodeId,
            formState: form.formState,
            isEditMode,
            editingIntegration,
          },
        );
        throw error;
      }
    },
    [
      onSubmit,
      createIntegration,
      updateIntegration,
      onClose,
      onSubmitSuccess,
      selectedNodeId,
      form.formState,
      isEditMode,
      editingIntegration,
    ],
  );

  const handleBack = React.useCallback(() => {
    setActiveStep(0);
    setSelectedNodeId(""); // Reset the selected node when going back
  }, []);

  const handleReset = React.useCallback(() => {
    setActiveStep(0);
    setSelectedNodeId("");
    form.reset(defaultFormValues);
  }, [form]);

  const handleNodeSelect = React.useCallback(
    (node: IntegrationNode) => {
      if (!node?.nodeId) return;

      const nodeId = node.nodeId;
      setSelectedNodeId(nodeId);

      const authType = node.auth?.authMethod || "apiKey";
      if (authType !== "apiKey" && authType !== "awsIam") return;

      form.reset({
        nodeId: nodeId,
        description: "",
        auth: {
          type: authType,
          credentials: {},
        },
      });

      // Automatically go to next step when node is selected
      setActiveStep(1);
    },
    [form],
  );

  // Reset form when modal closes or initialize for editing
  React.useEffect(() => {
    if (!open) {
      handleReset();
    } else if (isEditMode && editingIntegration) {
      // Initialize form for editing
      const config = editingIntegration.configuration || {};
      const authType = config.auth?.type || "apiKey";
      const credentials = config.auth?.credentials || {};

      // Try to construct nodeId from the integration type
      const nodeId =
        config.nodeId ||
        `node-${editingIntegration.type}-api` ||
        editingIntegration.type ||
        "";

      console.log("[IntegrationForm] Initializing edit mode:", {
        editingIntegration,
        config,
        authType,
        credentials,
        constructedNodeId: nodeId,
      });

      setSelectedNodeId(nodeId);
      form.reset({
        nodeId: nodeId,
        description: editingIntegration.description || config.description || "",
        auth: {
          type: authType,
          credentials: {
            apiKey: credentials.apiKey || "***existing***", // Placeholder for existing API key
            iamRole: credentials.iamRole || "",
          },
        },
      });

      // Skip to configuration step for editing
      setActiveStep(1);
    }
  }, [open, handleReset, isEditMode, editingIntegration, form]);

  const renderContent = () => {
    if (isLoadingNodes) {
      return (
        <Box sx={{ p: 2, textAlign: "center" }}>
          <Typography>{t("common.loading")}</Typography>
        </Box>
      );
    }

    if (activeStep === 0 && !isEditMode) {
      // Filter nodes based on search term
      const filteredNodes = nodes.filter((node) => {
        const searchTermLower = searchTerm.toLowerCase();
        return (
          node.info.title.toLowerCase().includes(searchTermLower) ||
          (node.info.description || "").toLowerCase().includes(searchTermLower)
        );
      });

      return (
        <Box>
          <TextField
            fullWidth
            placeholder={t("integrations.form.search.placeholder")}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            sx={{ mb: 2 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
            }}
          />
          <List
            sx={{
              maxHeight: 400,
              overflow: "auto",
              border: "1px solid",
              borderColor: "divider",
              borderRadius: 1,
              p: 0,
              mb: 3,
            }}
          >
            {filteredNodes.map((node) => {
              return (
                <ListItem key={node.nodeId} disablePadding>
                  <ListItemButton
                    selected={node.nodeId === selectedNodeId}
                    onClick={() => {
                      handleNodeSelect(node);
                    }}
                    sx={{
                      py: 2,
                      "&.Mui-selected": {
                        backgroundColor: "action.selected",
                        borderLeft: 4,
                        borderLeftColor: "primary.main",
                        pl: "12px",
                      },
                      "&:hover": {
                        backgroundColor: "action.hover",
                      },
                    }}
                  >
                    <ListItemIcon sx={{ minWidth: 56 }}>
                      <Avatar
                        alt={node.info.title}
                        src={`/icons/${node.nodeId}.svg`}
                        sx={{
                          width: 40,
                          height: 40,
                          bgcolor: "primary.main",
                        }}
                      >
                        {node.info.title?.charAt(0) || "?"}
                      </Avatar>
                    </ListItemIcon>
                    <ListItemText
                      primary={node.info.title}
                      secondary={node.info.description}
                      primaryTypographyProps={{
                        variant: "subtitle1",
                        fontWeight: node.nodeId === selectedNodeId ? 600 : 500,
                        color:
                          node.nodeId === selectedNodeId
                            ? "primary.main"
                            : "text.primary",
                      }}
                      secondaryTypographyProps={{
                        variant: "body2",
                        sx: {
                          display: "-webkit-box",
                          WebkitLineClamp: 2,
                          WebkitBoxOrient: "vertical",
                          overflow: "hidden",
                        },
                      }}
                    />
                  </ListItemButton>
                </ListItem>
              );
            })}
          </List>
          <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
            <Button onClick={onClose} variant="outlined">
              {t("common.cancel")}
            </Button>
          </Box>
        </Box>
      );
    }

    return (
      <IntegrationConfiguration
        formData={formValues}
        onSubmit={handleSubmit}
        onBack={handleBack}
        onClose={onClose}
        isEditMode={isEditMode}
      />
    );
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: "12px",
          minHeight: 400,
        },
      }}
    >
      <DialogTitle>
        <Typography variant="h6" component="div" sx={{ fontWeight: 600 }}>
          {isEditMode
            ? t("integrations.form.editTitle")
            : t("integrations.form.title")}
        </Typography>
      </DialogTitle>
      <DialogContent>
        <Box sx={{ mt: 2, mb: 4 }}>
          <Stepper activeStep={isEditMode ? 0 : activeStep}>
            {(isEditMode ? editSteps : createSteps).map((label) => (
              <Step key={label}>
                <StepLabel>{t(label)}</StepLabel>
              </Step>
            ))}
          </Stepper>
        </Box>
        {renderContent()}
      </DialogContent>
    </Dialog>
  );
};

export default IntegrationForm;
