import { z } from "zod";
import { FormFieldDefinition } from "../types";

// Create a WeakMap to store schemas using the fields array reference itself as the key
const schemaCache = new WeakMap<FormFieldDefinition[], z.ZodType>();

export const createZodSchema = (fields: FormFieldDefinition[]) => {
  // Check if we have a cached schema using the fields reference
  if (schemaCache.has(fields)) {
    return schemaCache.get(fields)!;
  }

  // If not in cache, create new schema
  const shape: Record<string, z.ZodTypeAny> = {};
  const parametersShape: Record<string, z.ZodTypeAny> = {};

  fields.forEach((field) => {
    const fieldName = field.name;
    let fieldSchema: z.ZodTypeAny;

    switch (field.type) {
      case "number":
        fieldSchema = z.coerce.number();
        break;
      case "switch":
        fieldSchema = z.boolean();
        break;
      case "select":
      case "multiselect":
        if (field.options) {
          const values = field.options.map((opt) => opt.value);
          fieldSchema =
            field.type === "multiselect"
              ? z.array(z.string())
              : z.string().refine((val) => values.includes(val), {
                  message: `Value must be one of: ${values.join(", ")}`,
                });
        } else {
          fieldSchema = field.type === "multiselect" ? z.array(z.string()) : z.string();
        }
        break;
      case "keyvalue":
        // Key-value editor stores an object { key: value, ... } or an array of rows.
        // Accept any record shape so the form doesn't reject the intermediate state.
        fieldSchema = z.record(z.string(), z.string()).or(z.array(z.any()));
        break;
      case "password":
      case "email":
      case "text":
      default:
        fieldSchema = z.string();
    }

    // Handle required/optional fields
    if (!field.required) {
      // An optional select's underlying control (e.g. a MUI Select bound to
      // a string) sits at "" — not undefined — until the user picks a value
      // or clears it. Without allowing the empty-string literal here, the
      // enum `refine` above rejects that natural "nothing selected" state
      // and blocks Save on an optional field that was never touched.
      fieldSchema =
        field.type === "select"
          ? z.union([fieldSchema, z.literal(""), z.undefined()]).optional()
          : z.union([fieldSchema, z.undefined()]).optional();
    } else {
      // For required fields, make them more lenient
      // Allow empty strings for text fields but mark them as required
      if (field.type === "text" || field.type === "email" || field.type === "password") {
        fieldSchema = z.string().optional().or(z.literal("")).or(z.undefined());
      } else if (field.type === "select") {
        // For select fields, allow empty strings or undefined
        fieldSchema = z.string().optional().or(z.literal("")).or(z.undefined());
      }
    }

    if (fieldName.startsWith("parameters.")) {
      const paramName = fieldName.replace("parameters.", "");
      parametersShape[paramName] = fieldSchema;
    } else {
      shape[fieldName] = fieldSchema;
    }
  });

  // Create the final schema
  const finalShape = {
    ...shape,
    parameters:
      Object.keys(parametersShape).length > 0
        ? z.object(parametersShape).passthrough()
        : z.record(z.string(), z.any()).optional(),
  };

  const schema = z.object(finalShape).passthrough();

  // Cache the schema using the fields reference
  schemaCache.set(fields, schema);

  return schema;
};
