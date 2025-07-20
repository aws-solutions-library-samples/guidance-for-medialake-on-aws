import React from "react";
import { Box, Button, Stack } from "@mui/material";
import { UseFormReturn } from "react-hook-form";
import { useTranslation } from "react-i18next";

interface FormProps {
  form: UseFormReturn<any>;
  onSubmit: (data: any) => Promise<void>;
  onCancel?: () => void;
  submitLabel?: string;
  children: React.ReactNode;
  showButtons?: boolean;
  id?: string;
}

export const Form: React.FC<FormProps> = React.memo(
  ({
    form,
    onSubmit,
    onCancel,
    submitLabel = "common.save",
    children,
    showButtons = true,
    id,
  }) => {
    const { t } = useTranslation();

    // Only log initial mount
    React.useEffect(() => {
      console.log("[Form] Mounted:", {
        formId: id,
        isValid: form.formState.isValid,
      });
    }, []);

    const handleSubmit = React.useCallback(
      async (data: any) => {
        console.log("[Form] Submitting form:", { formId: id });
        console.log("[Form] Form data to submit:", data);
        console.log("[Form] Form validation state:", {
          isValid: form.formState.isValid,
          isDirty: form.formState.isDirty,
          errors: form.formState.errors,
        });

        try {
          await onSubmit(data);
          console.log("[Form] Submit successful");
        } catch (error) {
          console.error("[Form] Submit failed:", error);
          throw error;
        }
      },
      [onSubmit, id],
    );

    const handleFormSubmit = React.useCallback(
      (e: React.FormEvent) => {
        e.preventDefault();
        return form.handleSubmit(handleSubmit)(e);
      },
      [form, handleSubmit],
    );

    const handleCancel = React.useCallback(() => {
      console.log("[Form] Cancelled");
      onCancel?.();
    }, [onCancel]);

    return (
      <Box
        component="form"
        id={id}
        onSubmit={handleFormSubmit}
        noValidate
        sx={{
          display: "flex",
          flexDirection: "column",
          gap: 2,
        }}
      >
        {children}
        {showButtons && (
          <Stack
            direction="row"
            spacing={2}
            justifyContent="flex-end"
            sx={{ mt: 2 }}
          >
            {onCancel && (
              <Button onClick={handleCancel} variant="outlined">
                {t("common.cancel")}
              </Button>
            )}
            <Button type="submit" variant="contained" color="primary">
              {t(submitLabel)}
            </Button>
          </Stack>
        )}
      </Box>
    );
  },
);

Form.displayName = "Form";
