/**
 * Centralized Schema Transformation Utility
 *
 * This utility ensures that ALL schema properties (like multiline, rows, min, max, etc.)
 * are preserved during parameter transformations across the application.
 *
 * IMPORTANT: This is the single source of truth for schema transformations.
 * Always use these functions when converting parameter schemas between formats.
 *
 * @module schemaTransformer
 */

/**
 /**
  * Normalizes parameter type strings to match our internal format
  *
  * IMPORTANT: Checks for options array to determine if field should be a select
  *
  * @param type - The type string from the API (e.g., 'string', 'integer')
  * @param schema - The full schema object (needed to check for options)
  * @returns Normalized type string (e.g., 'text', 'number', 'select')
  */
function normalizeType(type: string, schema?: any): string {
  // If the field has options, it should be rendered as a select dropdown
  if (schema?.options && Array.isArray(schema.options) && schema.options.length > 0) {
    return "select";
  }

  switch (type) {
    case "string":
      return "text";
    case "integer":
      return "number";
    default:
      return type;
  }
}
/**
 * Transforms a parameter from API format to internal format while preserving ALL schema properties.
 *
 * This function ensures that properties like multiline, rows, min, max, options, etc.
 * are never lost during transformation.
 *
 * @param param - Parameter object from the API
 * @returns Transformed parameter with all schema properties preserved
 *
 * @example
 * // Input from API
 * {
 *   name: "custom_prompt",
 *   label: "Custom Prompt",
 *   schema: { type: "string", multiline: true, rows: 6 }
 * }
 *
 * // Output (preserves multiline and rows)
 * {
 *   name: "custom_prompt",
 *   label: "Custom Prompt",
 *   schema: { type: "text", multiline: true, rows: 6 }
 * }
 */
export function transformParameterSchema(param: any): any {
  // Start with base parameter properties
  const transformed: any = {
    name: param.name,
    label: param.label || param.name,
    required: param.required || false,
    description: param.description || "",
  };

  // Preserve default value from various possible locations
  if (param.defaultValue !== undefined) {
    transformed.defaultValue = param.defaultValue;
  } else if (param.default !== undefined) {
    transformed.defaultValue = param.default;
  } else if (param.schema?.default !== undefined) {
    transformed.defaultValue = param.schema.default;
  }

  // Preserve showWhen for conditional field display
  if (param.showWhen) {
    transformed.showWhen = param.showWhen;
  }

  // Preserve placeholder text
  if (param.placeholder) {
    transformed.placeholder = param.placeholder;
  }

  // Handle schema transformation with property preservation
  if (param.schema) {
    const normalizedType = normalizeType(param.schema.type, param.schema);

    // CRITICAL: Use spread operator to preserve ALL existing schema properties
    transformed.schema = {
      ...param.schema, // Preserve everything first
      type: normalizedType, // Use normalized type
    };
  } else if (param.type) {
    // Handle legacy format where type is at param level
    transformed.schema = {
      type: normalizeType(param.type, param), // Pass param to check for options
    };

    // If there's a type at param level but no schema, preserve other param-level properties in schema
    if (param.multiline !== undefined) {
      transformed.schema.multiline = param.multiline;
    }
    if (param.rows !== undefined) {
      transformed.schema.rows = param.rows;
    }
    if (param.min !== undefined) {
      transformed.schema.min = param.min;
    }
    if (param.max !== undefined) {
      transformed.schema.max = param.max;
    }
  }

  // Ensure options are available at the transformed parameter level if they exist in schema
  if (param.schema?.options) {
    transformed.options = param.schema.options;
  } else if (param.options) {
    transformed.options = param.options;
    // Also add to schema if schema exists
    if (transformed.schema) {
      transformed.schema.options = param.options;
    }
  }

  return transformed;
}

/**
 * Transforms an array of parameters, preserving all schema properties
 *
 * @param parameters - Array of parameter objects from the API
 * @returns Array of transformed parameters
 */
export function transformParametersArray(parameters: any[]): any[] {
  if (!Array.isArray(parameters)) {
    console.warn("[schemaTransformer] Expected array but received:", typeof parameters);
    return [];
  }

  return parameters.map(transformParameterSchema);
}

/**
 * Transforms a parameters object (Record format) to an array format
 * while preserving all schema properties
 *
 * @param parameters - Parameters in Record<string, any> format
 * @returns Array of transformed parameters
 */
export function transformParametersRecordToArray(parameters: Record<string, any>): any[] {
  if (!parameters || typeof parameters !== "object") {
    console.warn("[schemaTransformer] Expected object but received:", typeof parameters);
    return [];
  }

  return Object.entries(parameters).map(([key, param]) => {
    // Ensure param has a name property
    const paramWithName = {
      ...param,
      name: param.name || key,
    };
    return transformParameterSchema(paramWithName);
  });
}

/**
 * Transforms object-type parameters by flattening nested properties
 * while preserving all schema properties
 *
 * @param param - Parameter with type="object" and properties
 * @returns Array of flattened parameters
 */
export function transformObjectParameter(param: any): any[] {
  if (!param.schema?.properties) {
    console.warn("[schemaTransformer] Object parameter has no properties:", param.name);
    return [];
  }

  const required = param.schema.required || [];

  return Object.entries(param.schema.properties).map(([propName, propSchema]: [string, any]) => ({
    name: propName,
    label: propSchema.label || propName.charAt(0).toUpperCase() + propName.slice(1),
    required: required.includes(propName),
    description: propSchema.description || "",
    defaultValue: propSchema.default,
    // Preserve ALL properties from propSchema
    schema: {
      ...propSchema,
      type: normalizeType(propSchema.type || "string", propSchema),
    },
    // Copy options to parameter level if they exist
    options: propSchema.options,
  }));
}

/**
 * Validates that schema properties were preserved during transformation
 * (Development mode only)
 *
 * @param original - Original parameter object
 * @param transformed - Transformed parameter object
 * @param context - Context string for logging (e.g., 'PipelineEditorPage')
 */
export function validateSchemaPreservation(original: any, transformed: any, context: string): void {
  if (process.env.NODE_ENV !== "development") return;

  const originalSchema = original.schema || {};
  const transformedSchema = transformed.schema || {};

  const originalKeys = new Set(Object.keys(originalSchema));
  const transformedKeys = new Set(Object.keys(transformedSchema));

  const lostKeys = Array.from(originalKeys).filter((key) => !transformedKeys.has(key));

  if (lostKeys.length > 0) {
    console.warn(
      `[${context}] Schema properties lost during transformation:`,
      lostKeys,
      "\nOriginal:",
      original,
      "\nTransformed:",
      transformed
    );
  }
}

/**
 * Helper function to ensure parameter has consistent structure
 * This is useful when parameters come from different sources with varying formats
 *
 * @param param - Parameter to normalize
 * @returns Parameter with consistent structure
 */
export function normalizeParameter(param: any): any {
  const normalized = transformParameterSchema(param);

  // Ensure schema exists
  if (!normalized.schema) {
    normalized.schema = {
      type: "text",
    };
  }

  // Validate in development
  if (process.env.NODE_ENV === "development") {
    validateSchemaPreservation(param, normalized, "normalizeParameter");
  }

  return normalized;
}
