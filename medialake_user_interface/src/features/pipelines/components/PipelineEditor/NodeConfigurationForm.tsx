import React, { useEffect, useMemo, useCallback } from "react";
import { Box, Typography } from "@mui/material";
import { useTranslation } from "react-i18next";
import { DynamicForm } from "../../../../forms/components/DynamicForm";
import { FormDefinition, FormFieldDefinition } from "../../../../forms/types";
import { NodeConfiguration, Node as NodeType, NodeParameter } from "@/features/pipelines/types";
import { useGetIntegrations } from "@/features/settings/integrations/api/integrations.controller";
import { useGetPipelines } from "../../api/pipelinesController";

interface NodeConfigurationFormProps {
  node: NodeType;
  configuration?: NodeConfiguration;
  onSubmit: (configuration: NodeConfiguration) => Promise<void>;
  onCancel?: () => void;
}

const mapParameterTypeToFormType = (type: string): FormFieldDefinition["type"] => {
  switch (type) {
    case "boolean":
      return "switch";
    case "number":
    case "integer":
      return "number";
    case "select":
      return "select";
    case "json_editor":
      return "json_editor";
    default:
      return "text";
  }
};

export const NodeConfigurationForm: React.FC<NodeConfigurationFormProps> = React.memo(
  ({ node, configuration, onSubmit, onCancel }) => {
    const { t } = useTranslation();
    const { data: integrationsData } = useGetIntegrations();
    const { data: pipelinesData } = useGetPipelines();

    // 1. Compute methodName.
    const methodName = useMemo(() => {
      if (node.info.nodeType === "TRIGGER") return "trigger";
      if (node.info.nodeType === "FLOW" && Array.isArray(node.methods) && node.methods.length > 0) {
        return configuration?.method || node.methods[0].name;
      }
      // For UTILITY and other nodes, if configuration.method is provided, use it;
      // otherwise, use the first available method key.
      return configuration?.method || (node.methods ? Object.keys(node.methods)[0] : "wait");
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
          return node.methods.find((m: any) => m.name === "trigger") || node.methods[0];
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
        return node.methods[configuration?.method || Object.keys(node.methods)[0]];
      }
      return undefined;
    }, [node.info.nodeType, node.methods, configuration?.method, methodName]);

    // 3. Compute flowParameters (for FLOW nodes).
    const flowParameters = useMemo(() => {
      if (node.info.nodeType === "FLOW") {
        if (Array.isArray(node.methods) && node.methods.length > 0) {
          return node.methods[0]?.config?.parameters || [];
        } else if (node.methods && typeof node.methods === "object") {
          const methodObj = node.methods[methodName] as any;
          return methodObj?.config?.parameters || [];
        }
      }
      // For non-FLOW nodes, use config parameters from methodInfo.
      return (methodInfo as any)?.config?.parameters || [];
    }, [node.info.nodeType, node.methods, methodName, methodInfo]);

    // 4. Compute effective parameters.
    const effectiveParameters = useMemo(() => {
      if (node.info.nodeType === "FLOW") {
        return Object.values(flowParameters);
      } else if (node.info.nodeType === "UTILITY") {
        // For UTILITY nodes, first check config.parameters.
        const configParams = (methodInfo as any)?.config?.parameters;

        // If configParams is an array with items, use it.
        if (Array.isArray(configParams) && configParams.length > 0) {
          return configParams;
        }

        // Otherwise, check if methodInfo.parameters exists.
        const topLevelParams = (methodInfo as any)?.parameters;

        if (Array.isArray(topLevelParams) && topLevelParams.length > 0) {
          return topLevelParams;
        }

        // If topLevelParams exists as an object, convert it to an array with proper structure.
        if (topLevelParams && typeof topLevelParams === "object") {
          const paramsArray = Object.entries(topLevelParams).map(([key, param]: [string, any]) => {
            return {
              ...param,
              name: key,
            };
          });

          return paramsArray;
        }

        // Finally, if configParams exists as an object, convert it.
        if (configParams && typeof configParams === "object") {
          const paramsArray = Object.values(configParams);
          return paramsArray;
        }

        return [];
      }

      // For TRIGGER or INTEGRATION nodes.
      const configParams = (methodInfo as any)?.config?.parameters;

      if (Array.isArray(configParams) && configParams.length > 0) {
        return configParams;
      }

      const topLevelParams = (methodInfo as any)?.parameters;

      if (Array.isArray(topLevelParams) && topLevelParams.length > 0) {
        return topLevelParams;
      }

      // If topLevelParams exists as an object, convert it to an array with proper structure.
      if (topLevelParams && typeof topLevelParams === "object") {
        const paramsArray = Object.entries(topLevelParams).map(([key, param]: [string, any]) => {
          return {
            ...param,
            name: key,
          };
        });

        return paramsArray;
      }

      // Finally, if configParams exists as an object, convert it.
      if (configParams && typeof configParams === "object") {
        const paramsArray = Object.values(configParams);
        return paramsArray;
      }

      return [];
    }, [node.info.nodeType, flowParameters, methodInfo, node.nodeId]);

    const hasParameters = useMemo(() => effectiveParameters.length > 0, [effectiveParameters]);

    // 5. Determine node type flags.
    const isIntegrationNode = useMemo(
      () => node.info.nodeType === "INTEGRATION",
      [node.info.nodeType]
    );
    const isTriggerNode = useMemo(() => node.info.nodeType === "TRIGGER", [node.info.nodeType]);
    const isFlowNode = useMemo(() => node.info.nodeType === "FLOW", [node.info.nodeType]);

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

      // Add integration field only for nodes that require external API integrations.
      // Nodes with auth.authMethod require an API key/external integration.
      // Bedrock and other AWS service nodes use IAM roles and don't need this field.
      if (isIntegrationNode) {
        const nodeAuth = (node as any).auth;
        const requiresExternalIntegration = nodeAuth && nodeAuth.authMethod;

        if (requiresExternalIntegration) {
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
                  message: t("common.validation.integrationMustBeSelected"),
                },
              ],
            },
          });
        }
      }

      // For TRIGGER, FLOW, and UTILITY nodes, use effectiveParameters.
      if (isTriggerNode || isFlowNode || node.info.nodeType === "UTILITY") {
        if (effectiveParameters.length > 0) {
          effectiveParameters.forEach((param: any) => {
            const field: FormFieldDefinition = {
              name: `parameters.${param.name}`,
              type: mapParameterTypeToFormType(param.schema?.type || "string"),
              label: param.label || param.name,
              required: param.required,
              tooltip: param.description,
            };

            // Copy showWhen for conditional field display
            if (param.showWhen) {
              field.showWhen = param.showWhen;
            }

            // Copy placeholder text
            if (param.placeholder) {
              field.placeholder = param.placeholder;
            }

            // Copy multiline and rows properties - check both param level and schema level
            if (param.multiline !== undefined) {
              field.multiline = param.multiline;
            } else if (param.schema?.multiline !== undefined) {
              field.multiline = param.schema.multiline;
            }

            if (param.rows !== undefined) {
              field.rows = param.rows;
            } else if (param.schema?.rows !== undefined) {
              field.rows = param.schema.rows;
            }

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

              // Use multiselect when schema.multiple is true
              if (param.schema?.multiple || param.multiple) {
                field.type = "multiselect";
              } else {
                field.type = "select";
              }

              if (field.required) {
                field.validation = {
                  type: "string",
                  rules: [
                    {
                      type: "regex",
                      value: ".+",
                      message: t("common.validation.fieldRequired"),
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
        Object.entries(methodInfo.parameters).forEach(([key, param]: [string, NodeParameter]) => {
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
                  message: t("common.validation.fieldRequired"),
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
        });
      }

      if (isTriggerNode) {
        const workflowField = fields.find((field) => field.name === "parameters.pipeline_name");
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
          let method;
          let path = "";
          let operationId = "";
          let requestMapping = null;
          let responseMapping = null;
          if (node.info.nodeType === "TRIGGER" || node.info.nodeType === "FLOW") {
            method = methodName;
          } else if (node.info.nodeType === "INTEGRATION") {
            method = methodName;
            const methodConfig = (methodInfo as any)?.config;
            if (methodConfig) {
              path = methodConfig.path || "";
              operationId = methodConfig.operationId || "";
              requestMapping = methodConfig.requestMapping || null;
              responseMapping = methodConfig.responseMapping || null;
            }
          } else {
            const opId = (methodInfo as any)?.config?.operationId;
            method = opId || methodName;
          }
          const config: NodeConfiguration = {
            method: method,
            parameters: data.parameters || {},
            integrationId: isIntegrationNode ? data.integrationId : undefined,
            path: path || configuration?.path || "",
            operationId: operationId || configuration?.operationId || "",
            requestMapping:
              requestMapping !== null ? requestMapping : configuration?.requestMapping,
            responseMapping:
              responseMapping !== null ? responseMapping : configuration?.responseMapping,
          };
          try {
            await onSubmit(config);
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
      ]
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
      const values = {
        parameters: configuration?.parameters || {},
        integrationId: isIntegrationNode ? configuration?.integrationId : undefined,
      };

      if (isIntegrationNode && !values.integrationId && integrationOptions.length > 0) {
        values.integrationId = integrationOptions[0].value;
      }

      // Handle default values for UTILITY, FLOW, TRIGGER, and INTEGRATION nodes from effectiveParameters
      if (
        (node.info.nodeType === "UTILITY" || isFlowNode || isTriggerNode || isIntegrationNode) &&
        effectiveParameters.length > 0
      ) {
        effectiveParameters.forEach((param: any) => {
          const paramName = param.name;

          let defaultValue =
            param.defaultValue !== undefined
              ? param.defaultValue
              : param.default !== undefined
                ? param.default
                : param.schema?.default !== undefined
                  ? param.schema.default
                  : param.default_value !== undefined
                    ? param.default_value
                    : undefined;

          // Check if this is a select parameter
          const isSelectParam = param.schema?.type === "select" || param.type === "select";
          const options = param.schema?.options || param.options || [];

          // For select parameters with options but no default, use the first option
          if (
            isSelectParam &&
            options.length > 0 &&
            defaultValue === undefined &&
            !values.parameters[paramName]
          ) {
            const firstOption = options[0];
            defaultValue = typeof firstOption === "object" ? firstOption.value : firstOption;
          }

          // Only set default if it's not already set in configuration
          if (defaultValue !== undefined && !values.parameters[paramName]) {
            // Skip setting default values for number fields when they are template variables
            const isNumberField =
              param.schema?.type === "number" || param.schema?.type === "integer";
            const isTemplateVariable =
              typeof defaultValue === "string" &&
              defaultValue.startsWith("${") &&
              defaultValue.endsWith("}");

            if (isNumberField && isTemplateVariable) {
              // Skip template variable defaults for number fields
            } else {
              values.parameters = {
                ...values.parameters,
                [paramName]: defaultValue,
              };
            }
          }
        });
      }

      // Handle default values from methodInfo.parameters for other node types
      if (methodInfo?.parameters) {
        Object.entries(methodInfo.parameters).forEach(([key, param]: [string, NodeParameter]) => {
          // Check for select parameters in both possible formats
          const isSelectParam = param.type === "select" || (param as any).schema?.type === "select";
          const options = (param as any).options || (param as any).schema?.options || [];

          if (isSelectParam && options.length > 0 && !values.parameters[key]) {
            const firstOption = options[0];
            const optionValue = typeof firstOption === "object" ? firstOption.value : firstOption;

            values.parameters = {
              ...values.parameters,
              [key]: optionValue || "",
            };
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
        });
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
  }
);

NodeConfigurationForm.displayName = "NodeConfigurationForm";

export default NodeConfigurationForm;
