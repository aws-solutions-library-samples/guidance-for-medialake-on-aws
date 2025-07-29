export interface NodeParameter {
  name: string;
  label: string;
  type: "text" | "number" | "boolean" | "select";
  required: boolean;
  description?: string;
}

export interface NodeMethod {
  name: string;
  description: string;
  parameters?: Record<string, NodeParameter>;
}

export interface NodeInfo {
  enabled: boolean;
  categories: string[];
  updatedAt: string;
  nodeType: string;
  iconUrl: string;
  description: string;
  tags: string[];
  title: string;
  inputTypes: string[];
  outputTypes: string[];
  createdAt: string;
}

export interface NodeConfiguration {
  method: string;
  parameters: Record<string, any>;
  requestMapping?: string;
  responseMapping?: string;
  path?: string;
  operationId?: string;
  integrationId?: string;
}

// Helper function to ensure numeric values remain as numbers
export const ensureCorrectTypes = (
  config: NodeConfiguration,
): NodeConfiguration => {
  if (!config || !config.parameters) return config;

  const processedParams: Record<string, any> = {};

  // Process each parameter
  Object.entries(config.parameters).forEach(([key, value]) => {
    // Handle numeric parameters
    if (typeof value === "string" && !isNaN(Number(value))) {
      // Check if this is a numeric parameter by looking at its schema
      const paramDef = Object.values(config.parameters).find(
        (p: any) => p?.name === key && p?.schema?.type === "number",
      );

      if (paramDef || key === "ConcurrencyLimit") {
        processedParams[key] = Number(value);
      } else {
        processedParams[key] = value;
      }
    } else if (
      typeof value === "object" &&
      value !== null &&
      value.schema?.type === "number" &&
      value.default !== undefined
    ) {
      // Handle parameter definitions with numeric defaults
      processedParams[key] = {
        ...value,
        default:
          typeof value.default === "string" && !isNaN(Number(value.default))
            ? Number(value.default)
            : value.default,
      };
    } else {
      processedParams[key] = value;
    }
  });

  return {
    ...config,
    parameters: processedParams,
  };
};

export interface CustomNodeData {
  id: string;
  type: string;
  label: string;
  configuration?: NodeConfiguration;
  inputTypes: string[];
  outputTypes: string[];
}

export interface Node {
  nodeId: string;
  info: NodeInfo;
  methods: Record<string, NodeMethod>;
}
