import React from "react";
import { Box } from "@mui/material";
import { Form } from "./Form";
import { FormField } from "./FormField";
import { FormSelect } from "./FormSelect";
import { FormSwitch } from "./FormSwitch";
import { FormJsonEditor } from "./FormJsonEditor";
import { useFormWithValidation } from "../hooks/useFormWithValidation";
import { FormDefinition, FormFieldDefinition } from "../types";
import { createZodSchema } from "../utils/createZodSchema";
import "zod";

interface DynamicFormProps {
  definition: FormDefinition;
  defaultValues?: Record<string, any>;
  onSubmit: (data: any) => Promise<void>;
  onCancel?: () => void;
  showButtons?: boolean;
}

export const DynamicForm: React.FC<DynamicFormProps> = React.memo(
  ({ definition, defaultValues, onSubmit, onCancel, showButtons = true }) => {
    // Only log initial mount
    React.useEffect(() => {
      console.log("[DynamicForm] Mounted:", {
        formId: definition.id,
        hasDefaultValues: !!defaultValues,
      });
    }, []);

    // Create a stable reference for fields
    const fields = React.useMemo(
      () => definition.fields,
      // Use JSON.stringify to compare deep equality
      [JSON.stringify(definition.fields)]
    );

    // Create schema using cached version
    const schema = React.useMemo(() => createZodSchema(fields), [fields]);

    const form = useFormWithValidation({
      validationSchema: schema,
      defaultValues: defaultValues || { parameters: {} },
      mode: "onBlur",
      reValidateMode: "onBlur",
    });

    // Render fields - NOT memoized so it re-evaluates when watched values change
    const renderField = definition.fields.map((field: FormFieldDefinition) => {
      if (field.showWhen) {
        const dependentValue = form.watch(field.showWhen.field);

        // DEBUG: Log conditional field evaluation
        console.log(`[DynamicForm] Conditional field evaluation:`, {
          fieldName: field.name,
          fieldLabel: field.label,
          showWhenField: field.showWhen.field,
          showWhenValue: field.showWhen.value,
          currentValue: dependentValue,
          shouldShow: dependentValue === field.showWhen.value,
          allFormValues: form.getValues(),
        });

        if (dependentValue !== field.showWhen.value) {
          console.log(
            `[DynamicForm] Hiding field ${field.name} because ${dependentValue} !== ${field.showWhen.value}`
          );
          return null;
        }
        console.log(`[DynamicForm] Showing field ${field.name} because condition matched`);
      }

      // Common props for all field types
      const commonProps = {
        key: field.name,
        name: field.name,
        control: form.control,
        label: field.label, // Use direct label
        tooltip: field.tooltip,
        required: field.required,
        useDirectLabels: true, // New prop to bypass i18n
        ...(field.placeholder !== undefined && {
          placeholder: field.placeholder,
        }),
        ...(field.multiline !== undefined && { multiline: field.multiline }),
        ...(field.rows !== undefined && { rows: field.rows }),
      };

      switch (field.type) {
        case "select":
          return <FormSelect {...commonProps} options={field.options || []} />;

        case "multiselect":
          return <FormSelect {...commonProps} options={field.options || []} multiple />;

        case "switch":
          return <FormSwitch {...commonProps} />;

        case "json_editor":
          return <FormJsonEditor {...commonProps} />;

        default:
          return <FormField {...commonProps} type={field.type} />;
      }
    });

    const handleSubmit = React.useCallback(
      async (data: any) => {
        console.log("[DynamicForm] Submitting form with data:", data);
        try {
          // Parse and validate
          const validatedData = schema.safeParse(data);

          if (!validatedData.success) {
            console.error("[DynamicForm] Validation failed:", validatedData.error);
            console.error("[DynamicForm] Validation errors:", validatedData.error.errors);
            console.error("[DynamicForm] Form data that failed validation:", data);

            // Try to submit anyway with the original data
            console.warn(
              "[DynamicForm] Attempting to submit with original data despite validation errors"
            );
            try {
              await onSubmit(data);
              console.log("[DynamicForm] Submit successful despite validation errors");
              return;
            } catch (submitError) {
              console.error("[DynamicForm] Submit failed with original data:", submitError);
              throw validatedData.error;
            }
          }

          console.log("[DynamicForm] Validation successful, submitting data:", validatedData.data);
          await onSubmit(validatedData.data);
        } catch (error) {
          console.error("[DynamicForm] Submit error:", error);
          throw error;
        }
      },
      [onSubmit, schema]
    );

    // Only log errors and submission state
    React.useEffect(() => {
      if (form.formState.errors && Object.keys(form.formState.errors).length > 0) {
        console.log("[DynamicForm] Form errors:", form.formState.errors);
      }
    }, [form.formState.errors]);

    return (
      <Form
        form={form}
        onSubmit={handleSubmit}
        onCancel={onCancel}
        showButtons={showButtons}
        id={definition.id}
      >
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>{renderField}</Box>
      </Form>
    );
  }
);

DynamicForm.displayName = "DynamicForm";
