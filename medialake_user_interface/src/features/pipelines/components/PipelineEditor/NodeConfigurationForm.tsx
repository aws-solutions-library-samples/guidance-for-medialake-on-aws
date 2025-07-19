import React, { useEffect, useMemo, useCallback } from "react";
import { Box, Typography } from "@mui/material";
import { useTranslation } from "react-i18next";
import { DynamicForm } from "../../../../forms/components/DynamicForm";
import { FormDefinition, FormFieldDefinition } from "../../../../forms/types";
import {
  NodeConfiguration,
  Node as NodeType,
  NodeParameter,
} from "@/features/pipelines/types";
import { useGetIntegrations } from "@/features/settings/integrations/api/integrations.controller";
import { useGetPipelines } from "../../api/pipelinesController";

interface NodeConfigurationFormProps {
  node: NodeType;
  configuration?: NodeConfiguration;
  onSubmit: (configuration: NodeConfiguration) => Promise<void>;
  onCancel?: () => void;
}

const mapParameterTypeToFormType = (
  type: string,
): FormFieldDefinition["type"] => {
  switch (type) {
    case "boolean":
      return "switch";
    case "number":
      return "number";
    case "select":
      return "select";
    default:
      return "text";
  }
};

export const NodeConfigurationForm: React.FC<NodeConfigurationFormProps> =
  React.memo(({ node, configuration, onSubmit, onCancel }) => {
    const { t } = useTranslation();
    const { data: integrationsData } = useGetIntegrations();
    const { data: pipelinesData } = useGetPipelines();

    // 1. Compute methodName.
    const methodName = useMemo(() => {
      if (node.info.nodeType === "TRIGGER") return "trigger";
      if (
        node.info.nodeType === "FLOW" &&
        Array.isArray(node.methods) &&
        node.methods.length > 0
      ) {
        return configuration?.method || node.methods[0].name;
      }
      // For UTILITY and other nodes, if configuration.method is provided, use it;
      // otherwise, use the first available method key.
      return (
        configuration?.method ||
        (node.methods ? Object.keys(node.methods)[0] : "wait")
      );
    }, [node.methods, configuration, node.info.nodeType]);

    // 2. Compute methodInfo with an explicit branch for UTILITY nodes.
    const methodInfo = useMemo(() => {
      if (node.info.nodeType === "FLOW") {
        if (Array.isArray(node.methods) && node.methods.length > 0) {
          return node.methods[0];
        } else if (node.methods && typeof node.methods === "object") {
          return node.methods[methodName];
        }
      }
      if (node.info.nodeType === "TRIGGER") {
        if (Array.isArray(node.methods)) {
          return (
            node.methods.find((m: any) => m.name === "trigger") ||
            node.methods[0]
          );
        } else if (typeof node.methods === "object") {
          const methods = Object.values(node.methods);
          return methods.find((m: any) => m.name === "trigger") || methods[0];
        }
      }
      if (node.info.nodeType === "UTILITY") {
        // For utility nodes, simply return the first method.
        if (Array.isArray(node.methods) && node.methods.length > 0) {
          return node.methods[0];
        } else if (node.methods && typeof node.methods === "object") {
          return node.methods[Object.keys(node.methods)[0]];
        }
      }
      // Fallback for other node types.
      if (Array.isArray(node.methods)) {
        const index = configuration?.method
          ? node.methods.findIndex((m: any) => m.name === configuration.method)
          : 0;
        return node.methods[index];
      } else if (typeof node.methods === "object") {
        return node.methods[
          configuration?.method || Object.keys(node.methods)[0]
        ];
      }
      return undefined;
    }, [node.info.nodeType, node.methods, configuration?.method, methodName]);

    // 3. Compute flowParameters (for FLOW nodes).
    const flowParameters = useMemo(() => {
      if (node.info.nodeType === "FLOW") {
        if (Array.isArray(node.methods) && node.methods.length > 0) {
          console.log(
            "FLOW node detected (array). Using original config parameters:",
            node.methods[0]?.config?.parameters,
          );
          return node.methods[0]?.config?.parameters || [];
        } else if (node.methods && typeof node.methods === "object") {
          const methodObj = node.methods[methodName] as any;
          console.log(
            "FLOW node detected (object). Using config parameters from key",
            methodName,
            ":",
            methodObj?.config?.parameters,
          );
          return methodObj?.config?.parameters || [];
        }
      }
      // For non-FLOW nodes, use config parameters from methodInfo.
      return (methodInfo as any)?.config?.parameters || [];
    }, [node.info.nodeType, node.methods, methodName, methodInfo]);

    // 4. Compute effective parameters.
    const effectiveParameters = useMemo(() => {
      console.log(
        "[NodeConfigurationForm] Computing effective parameters for node type:",
        node.info.nodeType,
      );
      console.log("[NodeConfigurationForm] Node ID:", node.nodeId);

      if (node.info.nodeType === "FLOW") {
        return Object.values(flowParameters);
      } else if (node.info.nodeType === "UTILITY") {
        // For UTILITY nodes, first check config.parameters.
        const configParams = (methodInfo as any)?.config?.parameters;
        console.log(
          "[NodeConfigurationForm] UTILITY node configParams:",
          configParams,
        );

        // If configParams is an array with items, use it.
        if (Array.isArray(configParams) && configParams.length > 0) {
          console.log(
            "[NodeConfigurationForm] Using configParams array:",
            configParams,
          );
          return configParams;
        }

        // Otherwise, check if methodInfo.parameters exists.
        const topLevelParams = (methodInfo as any)?.parameters;
        console.log(
          "[NodeConfigurationForm] UTILITY node topLevelParams:",
          topLevelParams,
        );

        if (Array.isArray(topLevelParams) && topLevelParams.length > 0) {
          console.log(
            "[NodeConfigurationForm] Using topLevelParams array:",
            topLevelParams,
          );
          return topLevelParams;
        }

        // If topLevelParams exists as an object, convert it to an array with proper structure.
        if (topLevelParams && typeof topLevelParams === "object") {
          // Transform parameters to ensure consistent structure
          const paramsArray = Object.entries(topLevelParams).map(
            ([key, param]: [string, any]) => {
              // Create a new parameter with consistent structure
              const transformedParam: any = {
                name: key,
                label: param.label || key,
                required: param.required || false,
                description: param.description || "",
              };

              // Handle select parameters specifically
              if (param.type === "select") {
                transformedParam.schema = {
                  type: "select",
                  options: param.options || [],
                };
              } else {
                // For other parameter types
                transformedParam.schema = {
                  type: param.type || "string",
                };
              }

              return transformedParam;
            },
          );

          console.log(
            "[NodeConfigurationForm] Using transformed topLevelParams:",
            paramsArray,
          );
          return paramsArray;
        }

        // Finally, if configParams exists as an object, convert it.
        if (configParams && typeof configParams === "object") {
          const paramsArray = Object.values(configParams);
          console.log(
            "[NodeConfigurationForm] Using configParams object converted to array:",
            paramsArray,
          );
          return paramsArray;
        }

        console.log(
          "[NodeConfigurationForm] No parameters found for UTILITY node",
        );
        return [];
      }

      // For TRIGGER or INTEGRATION nodes.
      const params = (methodInfo as any)?.config?.parameters || [];
      console.log(
        "[NodeConfigurationForm] TRIGGER/INTEGRATION node parameters:",
        params,
      );
      return params;
    }, [node.info.nodeType, flowParameters, methodInfo, node.nodeId]);

    const hasParameters = useMemo(
      () => effectiveParameters.length > 0,
      [effectiveParameters],
    );

    // 5. Determine node type flags.
    const isIntegrationNode = useMemo(
      () => node.info.nodeType === "INTEGRATION",
      [node.info.nodeType],
    );
    const isTriggerNode = useMemo(
      () => node.info.nodeType === "TRIGGER",
      [node.info.nodeType],
    );
    const isFlowNode = useMemo(
      () => node.info.nodeType === "FLOW",
      [node.info.nodeType],
    );

    const integrationOptions = useMemo(() => {
      if (!integrationsData?.data) return [];
      return integrationsData.data.map((integration) => ({
        label: integration.name,
        value: integration.id,
      }));
    }, [integrationsData]);

    const pipelinesOptions = useMemo(() => {
      if (!pipelinesData?.data?.s) return [];
      return pipelinesData.data.s.map((pipeline) => ({
        label: pipeline.name,
        value: pipeline.id,
      }));
    }, [pipelinesData]);

    // 6. Build form definition.
    const formDefinition = useMemo<FormDefinition>(() => {
      const fields: FormFieldDefinition[] = [];

      // Add integration field if needed.
      if (isIntegrationNode) {
        fields.push({
          name: "integrationId",
          type: "select",
          label: "Select Integration",
          tooltip: "Select an integration for this node",
          required: true,
          options: integrationOptions,
          validation: {
            type: "string",
            rules: [
              {
                type: "regex",
                value: ".+",
                message: "An integration must be selected",
              },
            ],
          },
        });
      }

      // For TRIGGER, FLOW, and UTILITY nodes, use effectiveParameters.
      if (isTriggerNode || isFlowNode || node.info.nodeType === "UTILITY") {
        console.log("Effective method parameters:", effectiveParameters);
        if (effectiveParameters.length > 0) {
          effectiveParameters.forEach((param: any) => {
            const field: FormFieldDefinition = {
              name: `parameters.${param.name}`,
              type: mapParameterTypeToFormType(param.schema?.type || "string"),
              label: param.label || param.name,
              required: param.required,
              tooltip: param.description,
            };
            // Determine parameter type from either schema.type or direct type
            const paramType = param.schema?.type || param.type || "string";

            // Check for select parameters in both formats
            if (
              paramType === "select" &&
              ((param.schema?.options && param.schema.options.length > 0) ||
                (param.options && param.options.length > 0))
            ) {
              // Get options from either schema.options or direct options
              const optionsArray = param.schema?.options || param.options || [];

              const options = optionsArray.map((opt: any) => ({
                label: typeof opt === "object" ? opt.label || opt.value : opt,
                value: typeof opt === "object" ? opt.value : opt,
              }));

              field.options = options;
              field.type = "select";

              if (field.required) {
                field.validation = {
                  type: "string",
                  rules: [
                    {
                      type: "regex",
                      value: ".+",
                      message: "This field is required",
                    },
                  ],
                };
              }
            }
            fields.push(field);
          });
        }
      } else if (methodInfo?.parameters) {
        // For any other node type, fallback to using methodInfo.parameters.
        Object.entries(methodInfo.parameters).forEach(
          ([key, param]: [string, NodeParameter]) => {
            const field: FormFieldDefinition = {
              name: `parameters.${key}`,
              type: mapParameterTypeToFormType(param.type),
              label: param.label || key,
              required: param.required,
              tooltip: param.description,
            };
            if (param.required) {
              field.validation = {
                type: param.type === "number" ? "number" : "string",
                rules: [
                  {
                    type: "regex",
                    value: ".+",
                    message: "This field is required",
                  },
                ],
              };
            }
            if (param.type === "select" && "options" in param) {
              const options =
                (param as any).options?.map((opt: any) => ({
                  label: opt.label || opt,
                  value: opt.value || opt,
                })) || [];
              field.options = options;
            }
            fields.push(field);
          },
        );
      }

      if (isTriggerNode) {
        const workflowField = fields.find(
          (field) => field.name === "parameters.pipeline_name",
        );
        if (workflowField) {
          Object.assign(workflowField, { options: pipelinesOptions });
        }
      }

      return {
        id: `node-config-${node.nodeId}-form`,
        name: node.info.title,
        description: node.info.description,
        fields,
      };
    }, [
      node.nodeId,
      node.info.title,
      node.info.description,
      effectiveParameters,
      isIntegrationNode,
      isTriggerNode,
      integrationOptions,
      pipelinesOptions,
      isFlowNode,
      methodInfo,
      node.info.nodeType,
    ]);

    const handleFormSubmit = useCallback(
      async (data: any) => {
        try {
          console.log("[NodeConfigurationForm] Form data:", data);
          console.log("[NodeConfigurationForm] methodInfo:", methodInfo);
          console.log("[NodeConfigurationForm] Node type:", node.info.nodeType);
          console.log("[NodeConfigurationForm] methodName:", methodName);
          let method;
          let path = "";
          let operationId = "";
          let requestMapping = null;
          let responseMapping = null;
          if (
            node.info.nodeType === "TRIGGER" ||
            node.info.nodeType === "FLOW"
          ) {
            method = methodName;
            console.log(
              "[NodeConfigurationForm] Using method name for trigger/flow node:",
              method,
            );
          } else if (node.info.nodeType === "INTEGRATION") {
            method = methodName;
            const methodConfig = (methodInfo as any)?.config;
            console.log("[NodeConfigurationForm] Method config:", methodConfig);
            if (methodConfig) {
              path = methodConfig.path || "";
              operationId = methodConfig.operationId || "";
              requestMapping = methodConfig.requestMapping || null;
              responseMapping = methodConfig.responseMapping || null;
            }
            console.log(
              "[NodeConfigurationForm] Using method name for integration node:",
              method,
            );
            console.log("[NodeConfigurationForm] Path:", path);
            console.log("[NodeConfigurationForm] OperationId:", operationId);
            console.log(
              "[NodeConfigurationForm] RequestMapping:",
              requestMapping,
            );
            console.log(
              "[NodeConfigurationForm] ResponseMapping:",
              responseMapping,
            );
          } else {
            const opId = (methodInfo as any)?.config?.operationId;
            method = opId || methodName;
            console.log(
              "[NodeConfigurationForm] Using operationId or method name:",
              method,
            );
          }
          const config: NodeConfiguration = {
            method: method,
            parameters: data.parameters || {},
            integrationId: isIntegrationNode ? data.integrationId : undefined,
            path: path || configuration?.path || "",
            operationId: operationId || configuration?.operationId || "",
            requestMapping:
              requestMapping !== null
                ? requestMapping
                : configuration?.requestMapping,
            responseMapping:
              responseMapping !== null
                ? responseMapping
                : configuration?.responseMapping,
          };
          console.log("[NodeConfigurationForm] Submitting config:", config);
          try {
            console.log(
              "[NodeConfigurationForm] Calling onSubmit with config:",
              JSON.stringify(config),
            );
            await onSubmit(config);
            console.log("[NodeConfigurationForm] Submit successful");
          } catch (submitError) {
            console.error("[NodeConfigurationForm] Submit error:", submitError);
          }
        } catch (error) {
          console.error("[NodeConfigurationForm] Submit failed:", error);
        }
      },
      [
        methodName,
        methodInfo,
        node.info.nodeType,
        configuration?.path,
        configuration?.operationId,
        configuration?.requestMapping,
        configuration?.responseMapping,
        onSubmit,
        isIntegrationNode,
      ],
    );

    // For nodes without parameters (excluding UTILITY), auto-submit.
    useEffect(() => {
      if (
        !hasParameters &&
        !isIntegrationNode &&
        !isTriggerNode &&
        !isFlowNode &&
        node.info.nodeType !== "UTILITY"
      ) {
        console.log(
          "[NodeConfigurationForm] Auto-submitting for node with no parameters",
        );
        let method;
        if (node.info.nodeType === "TRIGGER") {
          method = methodName;
        } else {
          const opId = (methodInfo as any)?.config?.operationId;
          method = opId || methodName;
        }
        const config: NodeConfiguration = {
          method: method,
          parameters: {},
          path: configuration?.path,
          operationId: configuration?.operationId,
          requestMapping: configuration?.requestMapping,
          responseMapping: configuration?.responseMapping,
        };
        console.log("[NodeConfigurationForm] Auto-submitting config:", config);
        onSubmit(config).catch(console.error);
      }
    }, [
      hasParameters,
      methodName,
      methodInfo,
      node.info.nodeType,
      configuration?.path,
      configuration?.operationId,
      configuration?.requestMapping,
      configuration?.responseMapping,
      onSubmit,
      isIntegrationNode,
      isTriggerNode,
      isFlowNode,
    ]);

    // For nodes without parameters (excluding UTILITY), show a "no configuration" message.
    if (
      !hasParameters &&
      !isIntegrationNode &&
      !isTriggerNode &&
      !isFlowNode &&
      node.info.nodeType !== "UTILITY"
    ) {
      return (
        <Box sx={{ p: 2, textAlign: "center" }}>
          <Typography variant="body1" color="text.secondary">
            {t("nodes.noConfiguration")}
          </Typography>
        </Box>
      );
    }

    const formDefaultValues = useMemo(() => {
      console.log("[NodeConfigurationForm] Computing form default values");
      console.log("[NodeConfigurationForm] Node type:", node.info.nodeType);
      console.log("[NodeConfigurationForm] Node ID:", node.nodeId);
      console.log(
        "[NodeConfigurationForm] Existing configuration:",
        configuration,
      );
      console.log(
        "[NodeConfigurationForm] Effective parameters:",
        effectiveParameters,
      );

      const values = {
        parameters: configuration?.parameters || {},
        integrationId: isIntegrationNode
          ? configuration?.integrationId
          : undefined,
      };

      console.log("[NodeConfigurationForm] Initial values:", values);

      if (
        isIntegrationNode &&
        !values.integrationId &&
        integrationOptions.length > 0
      ) {
        values.integrationId = integrationOptions[0].value;
      }

      // Handle default values for UTILITY, FLOW, and TRIGGER nodes from effectiveParameters
      if (
        (node.info.nodeType === "UTILITY" || isFlowNode || isTriggerNode) &&
        effectiveParameters.length > 0
      ) {
        console.log(
          "[NodeConfigurationForm] Processing defaults for",
          node.info.nodeType,
          "node",
        );

        effectiveParameters.forEach((param: any) => {
          console.log("[NodeConfigurationForm] Processing parameter:", param);
          const paramName = param.name;

          // Log all properties of the parameter to see what's available
          console.log(
            `[NodeConfigurationForm] Parameter ${paramName} properties:`,
            Object.keys(param),
          );

          // Check for default in different possible locations
          // The API response structure might vary, so we need to check multiple locations
          let defaultValue =
            param.default !== undefined
              ? param.default
              : param.schema?.default !== undefined
                ? param.schema.default
                : param.defaultValue !== undefined
                  ? param.defaultValue
                  : param.default_value !== undefined
                    ? param.default_value
                    : undefined;

          // Log the raw parameter to see its structure
          console.log(
            `[NodeConfigurationForm] Raw parameter object:`,
            JSON.stringify(param),
          );

          // Hardcode default values for specific parameters since they're not being properly passed
          if (
            node.nodeId === "pre_signed_url" &&
            param.name === "URL Validity Duration"
          ) {
            defaultValue = 3600;
            console.log(
              `[NodeConfigurationForm] Hardcoding default value for ${param.name} to:`,
              defaultValue,
            );
          }

          console.log(
            `[NodeConfigurationForm] Default value for ${paramName}:`,
            defaultValue,
          );

          // Check if this is a select parameter
          const isSelectParam =
            param.schema?.type === "select" || param.type === "select";
          const options = param.schema?.options || param.options || [];

          // For select parameters with options but no default, use the first option
          if (
            isSelectParam &&
            options.length > 0 &&
            defaultValue === undefined &&
            !values.parameters[paramName]
          ) {
            const firstOption = options[0];
            defaultValue =
              typeof firstOption === "object" ? firstOption.value : firstOption;
            console.log(
              `[NodeConfigurationForm] Using first option as default for select parameter ${paramName}:`,
              defaultValue,
            );
          }

          // Only set default if it's not already set in configuration
          if (defaultValue !== undefined && !values.parameters[paramName]) {
            values.parameters = {
              ...values.parameters,
              [paramName]: defaultValue,
            };
            console.log(
              `[NodeConfigurationForm] Setting default value for ${paramName}:`,
              defaultValue,
            );
          } else {
            console.log(
              `[NodeConfigurationForm] Not setting default for ${paramName}. Already set:`,
              values.parameters[paramName],
            );
          }
        });
      }

      // Handle default values from methodInfo.parameters for other node types
      if (methodInfo?.parameters) {
        Object.entries(methodInfo.parameters).forEach(
          ([key, param]: [string, NodeParameter]) => {
            // Check for select parameters in both possible formats
            const isSelectParam =
              param.type === "select" ||
              (param as any).schema?.type === "select";
            const options =
              (param as any).options || (param as any).schema?.options || [];

            if (
              isSelectParam &&
              options.length > 0 &&
              !values.parameters[key]
            ) {
              const firstOption = options[0];
              const optionValue =
                typeof firstOption === "object"
                  ? firstOption.value
                  : firstOption;

              values.parameters = {
                ...values.parameters,
                [key]: optionValue || "",
              };
              console.log(
                `[NodeConfigurationForm] Setting default for select parameter ${key}:`,
                optionValue,
              );
            }
            if (param.required && !values.parameters[key]) {
              if (param.type === "boolean") {
                values.parameters = {
                  ...values.parameters,
                  [key]: false,
                };
              } else if (param.type === "number") {
                values.parameters = {
                  ...values.parameters,
                  [key]: 0,
                };
              } else if (param.type !== "select") {
                values.parameters = {
                  ...values.parameters,
                  [key]: "",
                };
              }
            }
          },
        );
      }
      return values;
    }, [
      configuration?.parameters,
      configuration?.integrationId,
      isIntegrationNode,
      methodInfo,
      integrationOptions,
      node.info.nodeType,
      effectiveParameters,
      isFlowNode,
      isTriggerNode,
    ]);

    return (
      <Box>
        {node.info.title && (
          <Typography variant="h6" sx={{ mb: 3 }}>
            {node.info.title}
          </Typography>
        )}
        <DynamicForm
          definition={formDefinition}
          defaultValues={formDefaultValues}
          onSubmit={handleFormSubmit}
          onCancel={onCancel}
          showButtons={true}
        />
      </Box>
    );
  });

NodeConfigurationForm.displayName = "NodeConfigurationForm";

export default NodeConfigurationForm;
