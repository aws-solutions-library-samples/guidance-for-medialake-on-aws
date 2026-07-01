import React from "react";
import { Box } from "@mui/material";
import { Form } from "./Form";
import { FormField } from "./FormField";
import { FormSelect } from "./FormSelect";
import { FormSwitch } from "./FormSwitch";
import { useFormWithValidation } from "../hooks/useFormWithValidation";
import { FormDefinition, FormFieldDefinition } from "../types";
import { createZodSchema } from "../utils/createZodSchema";
import "zod";

// Lazy-load the JSON editor to avoid pulling vanilla-jsoneditor (~200KB) into the main bundle
const FormJsonEditor = React.lazy(() =>
  import("./FormJsonEditor").then((m) => ({ default: m.FormJsonEditor }))
);

// Lazy-load the KeyValueEditor so it's only pulled in when a node template
// declares a `keyvalue` parameter (currently only collection_manager).
const KeyValueEditor = React.lazy(() =>
  import("@/components/collections/KeyValueEditor").then((m) => ({
    default: m.KeyValueEditor,
  }))
);

interface DynamicFormProps {
  definition: FormDefinition;
  defaultValues?: Record<string, any>;
  onSubmit: (data: any) => Promise<void>;
  onCancel?: () => void;
  showButtons?: boolean;
}

export const DynamicForm: React.FC<DynamicFormProps> = React.memo(
  ({ definition, defaultValues, onSubmit, onCancel, showButtons = true }) => {
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

    // React Hook Form only applies `defaultValues` on mount. When the parent
    // recomputes defaults (e.g. after async node method data loads), we need
    // to push the new values into the form via `reset()`. Without this, the
    // form stays empty until the user manually interacts with it.
    const defaultValuesJson = JSON.stringify(defaultValues);
    React.useEffect(() => {
      if (defaultValues) {
        form.reset(defaultValues);
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [defaultValuesJson]);

    // Render fields - NOT memoized so it re-evaluates when watched values change
    const renderField = definition.fields.map((field: FormFieldDefinition) => {
      if (field.showWhen) {
        const dependentValue = form.watch(field.showWhen.field);

        if (field.showWhen.operator === "exists") {
          if (dependentValue === undefined || dependentValue === null || dependentValue === "") {
            return null;
          }
        } else {
          // `value` may be a single value or an array of accepted values
          // (e.g. a field shown for several operations). Support both.
          const expected = field.showWhen.value;
          const matches = Array.isArray(expected)
            ? expected.includes(dependentValue)
            : dependentValue === expected;
          if (!matches) {
            return null;
          }
        }
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
        ...(field.readOnly !== undefined && { readOnly: field.readOnly }),
      };

      switch (field.type) {
        case "select":
          return <FormSelect {...commonProps} options={field.options || []} />;

        case "multiselect":
          return <FormSelect {...commonProps} options={field.options || []} multiple />;

        case "switch":
          return <FormSwitch {...commonProps} />;

        case "json_editor":
          return (
            <React.Suspense key={field.name} fallback={<Box sx={{ height: 200 }} />}>
              <FormJsonEditor {...commonProps} />
            </React.Suspense>
          );

        case "keyvalue":
          return (
            <React.Suspense key={field.name} fallback={<Box sx={{ height: 80 }} />}>
              <Box>
                {field.label && (
                  <Box sx={{ mb: 0.5, fontSize: "0.875rem", fontWeight: 500 }}>{field.label}</Box>
                )}
                <KeyValueEditor
                  label=""
                  rows={(() => {
                    const val = form.watch(field.name);
                    if (Array.isArray(val)) return val;
                    if (val && typeof val === "object") {
                      return Object.entries(val).map(([key, value]) => ({
                        key,
                        value: String(value),
                      }));
                    }
                    return [];
                  })()}
                  onChange={(rows) => {
                    const obj: Record<string, string> = {};
                    for (const r of rows) {
                      if (r.key.trim()) obj[r.key.trim()] = r.value.trim();
                    }
                    form.setValue(field.name, obj, { shouldDirty: true });
                  }}
                />
              </Box>
            </React.Suspense>
          );

        default:
          return <FormField {...commonProps} type={field.type} />;
      }
    });

    const handleSubmit = React.useCallback(
      async (data: any) => {
        try {
          // Parse and validate
          const validatedData = schema.safeParse(data);

          if (!validatedData.success) {
            console.error("[DynamicForm] Validation failed:", validatedData.error);
            console.error("[DynamicForm] Validation errors:", validatedData.error.issues);
            console.error("[DynamicForm] Form data that failed validation:", data);

            // Try to submit anyway with the original data
            console.warn(
              "[DynamicForm] Attempting to submit with original data despite validation errors"
            );
            try {
              await onSubmit(data);
              return;
            } catch (submitError) {
              console.error("[DynamicForm] Submit failed with original data:", submitError);
              throw validatedData.error;
            }
          }

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
