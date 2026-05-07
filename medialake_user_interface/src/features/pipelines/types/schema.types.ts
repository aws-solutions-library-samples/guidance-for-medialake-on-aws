/**
 * TypeScript type definitions for parameter schemas
 *
 * These types ensure type safety and serve as documentation for
 * all possible schema properties across different parameter types.
 *
 * @module schema.types
 */

/**
 * Complete schema definition that includes all possible properties
 * for different parameter types (text, number, boolean, select, etc.)
 */
export interface ParameterSchema {
  /** The parameter type */
  type: "text" | "number" | "boolean" | "select" | "string" | "integer" | "object";

  // Text-specific properties
  /** Enable multiline text input (textarea) */
  multiline?: boolean;
  /** Number of rows for multiline text input */
  rows?: number;

  // Select-specific properties
  /** Options for select/dropdown fields */
  options?: string[] | Array<{ label: string; value: string }>;
  /** Allow multiple selections */
  multiple?: boolean;

  // Number-specific properties
  /** Minimum value for number inputs */
  min?: number;
  /** Maximum value for number inputs */
  max?: number;
  /** Step interval for number inputs */
  step?: number;

  // Object-specific properties
  /** Properties for object-type parameters */
  properties?: Record<string, ParameterSchema>;
  /** Required property names for object-type parameters */
  required?: string[];

  // Common properties
  /** Default value for the parameter */
  default?: any;
  /** Description of the parameter */
  description?: string;
  /** Enum values (alternative to options) */
  enum?: string[];
  /** Pattern for string validation */
  pattern?: string;
  /** Format hint (e.g., 'date', 'email', 'uri') */
  format?: string;
}

/**
 * Node parameter definition with full schema support
 */
export interface NodeParameter {
  /** Parameter name (unique identifier) */
  name: string;
  /** Display label for the parameter */
  label: string;
  /** Whether the parameter is required */
  required: boolean;
  /** Parameter description/help text */
  description: string;
  /** Default value for the parameter */
  defaultValue?: any;
  /** Complete parameter schema */
  schema: ParameterSchema;
  /** Options (duplicated from schema for convenience) */
  options?: string[] | Array<{ label: string; value: string }>;
  /** Legacy type property (for backward compatibility) */
  type?: string;
}

/**
 * Transformation result with validation info
 */
export interface TransformationResult {
  /** Transformed parameter */
  parameter: NodeParameter;
  /** Whether all properties were preserved */
  preserved: boolean;
  /** List of properties that were lost (if any) */
  lostProperties?: string[];
}
