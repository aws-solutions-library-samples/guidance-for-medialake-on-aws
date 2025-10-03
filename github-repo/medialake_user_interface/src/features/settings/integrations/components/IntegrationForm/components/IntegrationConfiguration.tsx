import React from "react";
import {
  Box,
  Button,
  IconButton,
  InputAdornment,
  FormControlLabel,
  Switch,
} from "@mui/material";
import { Visibility, VisibilityOff } from "@mui/icons-material";
import { useTranslation } from "react-i18next";
import { z } from "zod";
import { Form } from "@/forms/components/Form";
import { FormField } from "@/forms/components/FormField";
import { FormSelect } from "@/forms/components/FormSelect";
import { useFormWithValidation } from "@/forms/hooks/useFormWithValidation";
import {
  IntegrationConfigurationProps,
  IntegrationFormData,
} from "@/features/settings/integrations/components/IntegrationForm/types";

export const IntegrationConfiguration: React.FC<
  IntegrationConfigurationProps & { isEditMode?: boolean }
> = ({ formData, onSubmit, onBack, onClose, isEditMode = false }) => {
  const { t } = useTranslation();
  const [showApiKey, setShowApiKey] = React.useState(false);
  const [enabled, setEnabled] = React.useState(true);

  // Define schema directly with Zod
  const validationSchema = React.useMemo(() => {
    return z
      .object({
        nodeId: z.string().min(1, "Integration selection is required"),
        description: z.string().optional(), // Made optional
        auth: z.object({
          type: z.enum(["apiKey", "awsIam"]),
          credentials: z.object({
            apiKey: z.string().optional(),
            iamRole: z.string().optional(),
          }),
        }),
      })
      .strict()
      .refine(
        (data) => {
          // For apiKey auth type, require apiKey unless it's the placeholder for existing key
          if (data.auth.type === "apiKey") {
            const apiKey = data.auth.credentials.apiKey;
            return apiKey && (apiKey.length > 0 || apiKey === "***existing***");
          }
          return true;
        },
        {
          message: "API Key is required",
          path: ["auth", "credentials", "apiKey"],
        },
      );
  }, []);

  // Ensure form data matches schema structure exactly
  const initialFormData = React.useMemo(() => {
    console.log("[IntegrationConfiguration] Received form data:", formData);
    const cleanData = {
      nodeId: formData.nodeId || "",
      description: formData.description || "",
      auth: {
        type: formData.auth?.type || "apiKey",
        credentials: {
          apiKey: formData.auth?.credentials?.apiKey || "",
          iamRole: formData.auth?.credentials?.iamRole || "",
        },
      },
    };
    console.log("[IntegrationConfiguration] Cleaned form data:", cleanData);
    return cleanData;
  }, [formData]);

  const form = useFormWithValidation({
    defaultValues: initialFormData,
    validationSchema,
    mode: "onChange",
    translationPrefix: "integrations.form",
  });

  // Reset form only once when component mounts with initial data
  const [hasInitialized, setHasInitialized] = React.useState(false);
  const [lastNodeId, setLastNodeId] = React.useState("");

  React.useEffect(() => {
    // Reset if we have a new nodeId (different integration) or haven't initialized yet
    if (
      (!hasInitialized || lastNodeId !== initialFormData.nodeId) &&
      initialFormData.nodeId
    ) {
      console.log(
        "[IntegrationConfiguration] Initial form setup:",
        initialFormData,
      );
      form.reset(initialFormData);
      setHasInitialized(true);
      setLastNodeId(initialFormData.nodeId);
      // Trigger validation after reset
      setTimeout(() => {
        form.trigger();
      }, 0);
    }
  }, [initialFormData, form, hasInitialized, lastNodeId]);

  // Reset initialization when component unmounts or form closes
  React.useEffect(() => {
    return () => {
      setHasInitialized(false);
      setLastNodeId("");
    };
  }, []);

  React.useEffect(() => {
    // Log form state changes
    const subscription = form.watch((value) => {
      console.log("[IntegrationConfiguration] Form values changed:", value);
    });
    return () => subscription.unsubscribe();
  }, [form]);

  console.log("[IntegrationConfiguration] Current form state:", {
    values: form.getValues(),
    isValid: form.formState.isValid,
    isDirty: form.formState.isDirty,
    errors: form.formState.errors,
    errorDetails: JSON.stringify(form.formState.errors, null, 2),
  });

  const handleSubmit = React.useCallback(
    async (data: IntegrationFormData) => {
      // Close the form immediately before any validation or submission
      onClose();

      console.log(
        "[IntegrationConfiguration] Starting submission with data:",
        data,
      );
      try {
        const now = new Date().toISOString();

        // Handle the case where API key is the placeholder (not changed in edit mode)
        const submissionData = { ...data };
        if (data.auth.credentials.apiKey === "***existing***") {
          // Don't include the placeholder in the submission - let the backend keep the existing key
          submissionData.auth = {
            ...data.auth,
            credentials: {
              ...data.auth.credentials,
              apiKey: undefined, // Remove the placeholder
            },
          };
        }

        console.log(
          "[IntegrationConfiguration] Prepared submission data:",
          submissionData,
        );

        await onSubmit(submissionData);
        console.log("[IntegrationConfiguration] Submission completed");
      } catch (error) {
        console.error(
          "[IntegrationConfiguration] Error during submission:",
          error,
        );
        throw error; // Re-throw to allow parent component to handle the error
      }
    },
    [onSubmit, enabled, onClose],
  );

  const authMethod = formData.auth.type;

  return (
    <Form form={form} onSubmit={handleSubmit} showButtons={false}>
      <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <FormControlLabel
          control={
            <Switch
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              color="primary"
            />
          }
          label={t("integrations.form.fields.enabled.label")}
        />
        <FormField
          name="description"
          control={form.control}
          label={t("integrations.form.fields.description.label")}
          tooltip={t("integrations.form.fields.description.tooltip")}
          multiline
          rows={3}
          translationPrefix="integrations.form"
        />
        {authMethod === "awsIam" && (
          <FormField
            name="auth.credentials.iamRole"
            control={form.control}
            label={t("integrations.form.fields.iamRole.label")}
            tooltip={t("integrations.form.fields.iamRole.tooltip")}
            disabled
            value="IAM Role will be generated"
            translationPrefix="integrations.form"
          />
        )}
        {authMethod === "apiKey" && (
          <FormField
            name="auth.credentials.apiKey"
            control={form.control}
            label={t("integrations.form.fields.apiKey.label")}
            tooltip={t("integrations.form.fields.apiKey.tooltip")}
            type={showApiKey ? "text" : "password"}
            required
            translationPrefix="integrations.form"
            placeholder={
              formData.auth?.credentials?.apiKey === "***existing***"
                ? "Leave unchanged to keep existing API key"
                : "Enter your API key"
            }
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    onClick={() => setShowApiKey(!showApiKey)}
                    edge="end"
                  >
                    {showApiKey ? <VisibilityOff /> : <Visibility />}
                  </IconButton>
                </InputAdornment>
              ),
            }}
          />
        )}
      </Box>

      <Box
        sx={{
          mt: 4,
          display: "flex",
          justifyContent: isEditMode ? "flex-end" : "space-between",
        }}
      >
        {!isEditMode && (
          <Button onClick={onBack} variant="outlined">
            {t("common.back")}
          </Button>
        )}
        <Box sx={{ display: "flex", gap: 2 }}>
          <Button onClick={onClose} variant="outlined">
            {t("common.cancel")}
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={!form.formState.isValid}
          >
            {t("common.save")}
          </Button>
        </Box>
      </Box>
    </Form>
  );
};

export default React.memo(IntegrationConfiguration);
