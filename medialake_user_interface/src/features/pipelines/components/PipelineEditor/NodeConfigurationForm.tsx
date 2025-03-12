
// import React, { useEffect, useMemo, useCallback } from 'react';
// import { Box, Typography } from '@mui/material';
// import { useTranslation } from 'react-i18next';
// import { DynamicForm } from '../../../../forms/components/DynamicForm';
// import { FormDefinition, FormFieldDefinition } from '../../../../forms/types';
// import { NodeConfiguration, Node as NodeType, NodeParameter } from '@/features/pipelines/types';
// import { useGetIntegrations } from '@/features/settings/integrations/api/integrations.controller';
// import { useGetPipelines } from '../../api/pipelinesController';

// interface NodeConfigurationFormProps {
//   node: NodeType;
//   configuration?: NodeConfiguration;
//   onSubmit: (configuration: NodeConfiguration) => Promise<void>;
//   onCancel?: () => void;
// }

// const mapParameterTypeToFormType = (type: string): FormFieldDefinition['type'] => {
//   switch (type) {
//     case 'boolean': 
//       return 'switch';
//     case 'number': 
//       return 'number';
//     case 'select': 
//       return 'select';
//     default: 
//       return 'text';
//   }
// };

// export const NodeConfigurationForm: React.FC<NodeConfigurationFormProps> = React.memo(({
//   node,
//   configuration,
//   onSubmit,
//   onCancel,
// }) => {
//   const { t } = useTranslation();
//   const { data: integrationsData } = useGetIntegrations();
//   const { data: pipelinesData } = useGetPipelines();

//   // 1. Compute methodName first
//   const methodName = useMemo(() => {
//     if (node.info.nodeType === 'TRIGGER') return 'trigger';
//     if (node.info.nodeType === 'FLOW' && Array.isArray(node.methods) && node.methods.length > 0) {
//       return configuration?.method || node.methods[0].name;
//     }
//     return configuration?.method || (node.methods ? Object.keys(node.methods)[0] : 'wait');
//   }, [node.methods, configuration, node.info.nodeType]);

//   // 2. Now get the methodInfo before it is referenced later
//   const methodInfo = useMemo(() => {
//     if (node.info.nodeType === 'FLOW') {
//       if (Array.isArray(node.methods) && node.methods.length > 0) {
//         return node.methods[0];
//       } else if (node.methods && typeof node.methods === 'object') {
//         return node.methods[methodName];
//       }
//     }
//     if (node.info.nodeType === 'TRIGGER') {
//       if (Array.isArray(node.methods)) {
//         return node.methods.find((m: any) => m.name === 'trigger') || node.methods[0];
//       } else if (typeof node.methods === 'object') {
//         const methods = Object.values(node.methods);
//         return methods.find((m: any) => m.name === 'trigger') || methods[0];
//       }
//     }
//     if (Array.isArray(node.methods)) {
//       const index = configuration?.method
//         ? node.methods.findIndex((m: any) => m.name === configuration.method)
//         : 0;
//       return node.methods[index];
//     } else if (typeof node.methods === 'object') {
//       return node.methods[configuration?.method || Object.keys(node.methods)[0]];
//     }
//     return undefined;
//   }, [node.info.nodeType, node.methods, configuration?.method, methodName]);

//   // 3. Now compute flowParameters using methodInfo safely
//   const flowParameters = useMemo(() => {
//     if (node.info.nodeType === 'FLOW') {
//       if (Array.isArray(node.methods) && node.methods.length > 0) {
//         console.log(
//           "FLOW node detected (array). Using original config parameters:",
//           node.methods[0]?.config?.parameters
//         );
//         return node.methods[0]?.config?.parameters || [];
//       } else if (node.methods && typeof node.methods === 'object') {
//         const methodObj = node.methods[methodName] as any;
//         console.log(
//           "FLOW node detected (object). Using config parameters from key",
//           methodName,
//           ":",
//           methodObj?.config?.parameters
//         );
//         return methodObj?.config?.parameters || [];
//       }
//     }
//     // For non-FLOW nodes, use the config parameters if available.
//     return (methodInfo as any)?.config?.parameters || [];
//   }, [node.info.nodeType, node.methods, methodName, methodInfo]);

//   // 4. Compute effective parameters
//   const effectiveParameters = useMemo(() => {
//     if (node.info.nodeType === 'FLOW') {
//       // If flowParameters is an object, convert it into an array of its values.
//       return Object.values(flowParameters);
//     }
//     return (methodInfo as any)?.config?.parameters || [];
//   }, [node.info.nodeType, flowParameters, methodInfo]);

//   const hasParameters = useMemo(() => effectiveParameters.length > 0, [effectiveParameters]);

//   const isIntegrationNode = useMemo(() => node.info.nodeType === 'INTEGRATION', [node.info.nodeType]);
//   const isTriggerNode = useMemo(() => node.info.nodeType === 'TRIGGER', [node.info.nodeType]);
//   const isFlowNode = useMemo(() => node.info.nodeType === 'FLOW', [node.info.nodeType]);

//   const integrationOptions = useMemo(() => {
//     if (!integrationsData?.data) return [];
//     return integrationsData.data.map(integration => ({
//       label: integration.name,
//       value: integration.id,
//     }));
//   }, [integrationsData]);

//   const pipelinesOptions = useMemo(() => {
//     if (!pipelinesData?.data?.s) return [];
//     return pipelinesData.data.s.map(pipeline => ({
//       label: pipeline.name,
//       value: pipeline.id,
//     }));
//   }, [pipelinesData]);

//   const formDefinition = useMemo<FormDefinition>(() => {
//     const fields: FormFieldDefinition[] = [];

//     // Integration field if needed
//     if (isIntegrationNode) {
//       fields.push({
//         name: 'integrationId',
//         type: 'select',
//         label: 'Select Integration',
//         tooltip: 'Select an integration for this node',
//         required: true,
//         options: integrationOptions,
//         validation: {
//           type: 'string',
//           rules: [{
//             type: 'regex',
//             value: '.+',
//             message: 'An integration must be selected',
//           }],
//         },
//       });
//     }

//     // For FLOW and TRIGGER nodes, use the effectiveParameters
//     if (isTriggerNode || isFlowNode) {
//       console.log("Effective method parameters:", effectiveParameters);
//       if (effectiveParameters.length > 0) {
//         effectiveParameters.forEach((param: any) => {
//           const field: FormFieldDefinition = {
//             name: `parameters.${param.name}`,
//             type: mapParameterTypeToFormType(param.schema?.type || 'string'),
//             label: param.label || param.name,
//             required: param.required,
//             tooltip: param.description,
//           };
//           if (param.schema?.type === 'select' && param.schema?.options) {
//             const options = param.schema.options.map((opt: any) => ({
//               label: opt.label || opt,
//               value: opt.value || opt,
//             }));
//             field.options = options;
//             field.type = 'select';
//             if (field.required) {
//               field.validation = {
//                 type: 'string',
//                 rules: [{
//                   type: 'regex',
//                   value: '.+',
//                   message: 'This field is required',
//                 }],
//               };
//             }
//           }
//           fields.push(field);
//         });
//       }
//     } else if (methodInfo?.parameters) {
//       Object.entries(methodInfo.parameters).forEach(([key, param]: [string, NodeParameter]) => {
//         const field: FormFieldDefinition = {
//           name: `parameters.${key}`,
//           type: mapParameterTypeToFormType(param.type),
//           label: param.label || key,
//           required: param.required,
//           tooltip: param.description,
//         };
//         if (param.required) {
//           field.validation = {
//             type: param.type === 'number' ? 'number' : 'string',
//             rules: [{
//               type: 'regex',
//               value: '.+',
//               message: 'This field is required',
//             }],
//           };
//         }
//         if (param.type === 'select' && 'options' in param) {
//           const options = (param as any).options?.map((opt: any) => ({
//             label: opt.label || opt,
//             value: opt.value || opt,
//           })) || [];
//           field.options = options;
//         }
//         fields.push(field);
//       });
//     }

//     if (isTriggerNode) {
//       const workflowField = fields.find(field => field.name === 'parameters.pipeline_name');
//       if (workflowField) {
//         Object.assign(workflowField, { options: pipelinesOptions });
//       }
//     }

//     return {
//       id: `node-config-${node.nodeId}-form`,
//       name: node.info.title,
//       description: node.info.description,
//       fields,
//     };
//   }, [
//     node.nodeId,
//     node.info.title,
//     node.info.description,
//     effectiveParameters,
//     isIntegrationNode,
//     isTriggerNode,
//     integrationOptions,
//     pipelinesOptions,
//     isFlowNode,
//     methodInfo
//   ]);

//   const handleFormSubmit = useCallback(async (data: any) => {
//     try {
//       console.log('[NodeConfigurationForm] Form data:', data);
//       console.log('[NodeConfigurationForm] methodInfo:', methodInfo);
//       console.log('[NodeConfigurationForm] Node type:', node.info.nodeType);
//       console.log('[NodeConfigurationForm] methodName:', methodName);
//       let method;
//       let path = '';
//       let operationId = '';
//       let requestMapping = null;
//       let responseMapping = null;
//       if (node.info.nodeType === 'TRIGGER' || node.info.nodeType === 'FLOW') {
//         method = methodName;
//         console.log('[NodeConfigurationForm] Using method name for trigger/flow node:', method);
//       } else if (node.info.nodeType === 'INTEGRATION') {
//         method = methodName;
//         const methodConfig = (methodInfo as any)?.config;
//         console.log('[NodeConfigurationForm] Method config:', methodConfig);
//         if (methodConfig) {
//           path = methodConfig.path || '';
//           operationId = methodConfig.operationId || '';
//           requestMapping = methodConfig.requestMapping || null;
//           responseMapping = methodConfig.responseMapping || null;
//         }
//         console.log('[NodeConfigurationForm] Using method name for integration node:', method);
//         console.log('[NodeConfigurationForm] Path:', path);
//         console.log('[NodeConfigurationForm] OperationId:', operationId);
//         console.log('[NodeConfigurationForm] RequestMapping:', requestMapping);
//         console.log('[NodeConfigurationForm] ResponseMapping:', responseMapping);
//       } else {
//         const opId = (methodInfo as any)?.config?.operationId;
//         method = opId || methodName;
//         console.log('[NodeConfigurationForm] Using operationId or method name:', method);
//       }
//       const config: NodeConfiguration = {
//         method: method,
//         parameters: data.parameters || {},
//         integrationId: isIntegrationNode ? data.integrationId : undefined,
//         path: path || configuration?.path || '',
//         operationId: operationId || configuration?.operationId || '',
//         requestMapping: requestMapping !== null ? requestMapping : configuration?.requestMapping,
//         responseMapping: responseMapping !== null ? responseMapping : configuration?.responseMapping,
//       };
//       console.log('[NodeConfigurationForm] Submitting config:', config);
//       try {
//         console.log('[NodeConfigurationForm] Calling onSubmit with config:', JSON.stringify(config));
//         await onSubmit(config);
//         console.log('[NodeConfigurationForm] Submit successful');
//       } catch (submitError) {
//         console.error('[NodeConfigurationForm] Submit error:', submitError);
//       }
//     } catch (error) {
//       console.error('[NodeConfigurationForm] Submit failed:', error);
//     }
//   }, [methodName, methodInfo, node.info.nodeType, configuration?.path, configuration?.operationId, configuration?.requestMapping, configuration?.responseMapping, onSubmit, isIntegrationNode]);

//   useEffect(() => {
//     if (!hasParameters && !isIntegrationNode && !isTriggerNode && !isFlowNode) {
//       console.log('[NodeConfigurationForm] Auto-submitting for node with no parameters');
//       let method;
//       if (node.info.nodeType === 'TRIGGER') {
//         method = methodName;
//       } else {
//         const opId = (methodInfo as any)?.config?.operationId;
//         method = opId || methodName;
//       }
//       const config: NodeConfiguration = {
//         method: method,
//         parameters: {},
//         path: configuration?.path,
//         operationId: configuration?.operationId,
//         requestMapping: configuration?.requestMapping,
//         responseMapping: configuration?.responseMapping,
//       };
//       console.log('[NodeConfigurationForm] Auto-submitting config:', config);
//       onSubmit(config).catch(console.error);
//     }
//   }, [
//     hasParameters,
//     methodName,
//     methodInfo,
//     node.info.nodeType,
//     configuration?.path,
//     configuration?.operationId,
//     configuration?.requestMapping,
//     configuration?.responseMapping,
//     onSubmit,
//     isIntegrationNode,
//     isTriggerNode,
//     isFlowNode
//   ]);

//   if (!hasParameters && !isIntegrationNode && !isTriggerNode && !isFlowNode) {
//     return (
//       <Box sx={{ p: 2, textAlign: 'center' }}>
//         <Typography variant="body1" color="text.secondary">
//           {t('nodes.noConfiguration')}
//         </Typography>
//       </Box>
//     );
//   }

//   const formDefaultValues = useMemo(() => {
//     const values = {
//       parameters: configuration?.parameters || {},
//       integrationId: isIntegrationNode ? configuration?.integrationId : undefined,
//     };
//     if (isIntegrationNode && !values.integrationId && integrationOptions.length > 0) {
//       values.integrationId = integrationOptions[0].value;
//     }
//     if (methodInfo?.parameters) {
//       Object.entries(methodInfo.parameters).forEach(([key, param]: [string, NodeParameter]) => {
//         if (param.type === 'select' && 'options' in param) {
//           const options = (param as any).options || [];
//           if (!values.parameters[key] && options.length > 0) {
//             values.parameters = {
//               ...values.parameters,
//               [key]: options[0].value || '',
//             };
//           }
//         }
//         if (param.required && !values.parameters[key]) {
//           if (param.type === 'boolean') {
//             values.parameters = {
//               ...values.parameters,
//               [key]: false,
//             };
//           } else if (param.type === 'number') {
//             values.parameters = {
//               ...values.parameters,
//               [key]: 0,
//             };
//           } else if (param.type !== 'select') {
//             values.parameters = {
//               ...values.parameters,
//               [key]: '',
//             };
//           }
//         }
//       });
//     }
//     return values;
//   }, [configuration?.parameters, configuration?.integrationId, isIntegrationNode, methodInfo, integrationOptions]);

//   return (
//     <Box>
//       {node.info.title && (
//         <Typography variant="h6" sx={{ mb: 3 }}>
//           {node.info.title}
//         </Typography>
//       )}
//       <DynamicForm
//         definition={formDefinition}
//         defaultValues={formDefaultValues}
//         onSubmit={handleFormSubmit}
//         onCancel={onCancel}
//         showButtons={true}
//       />
//     </Box>
//   );
// });

// NodeConfigurationForm.displayName = 'NodeConfigurationForm';

// export default NodeConfigurationForm;


import React, { useEffect, useMemo, useCallback } from 'react';
import { Box, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { DynamicForm } from '../../../../forms/components/DynamicForm';
import { FormDefinition, FormFieldDefinition } from '../../../../forms/types';
import { NodeConfiguration, Node as NodeType, NodeParameter } from '@/features/pipelines/types';
import { useGetIntegrations } from '@/features/settings/integrations/api/integrations.controller';
import { useGetPipelines } from '../../api/pipelinesController';

interface NodeConfigurationFormProps {
  node: NodeType;
  configuration?: NodeConfiguration;
  onSubmit: (configuration: NodeConfiguration) => Promise<void>;
  onCancel?: () => void;
}

const mapParameterTypeToFormType = (type: string): FormFieldDefinition['type'] => {
  switch (type) {
    case 'boolean': 
      return 'switch';
    case 'number': 
      return 'number';
    case 'select': 
      return 'select';
    default: 
      return 'text';
  }
};

export const NodeConfigurationForm: React.FC<NodeConfigurationFormProps> = React.memo(({
  node,
  configuration,
  onSubmit,
  onCancel,
}) => {
  const { t } = useTranslation();
  const { data: integrationsData } = useGetIntegrations();
  const { data: pipelinesData } = useGetPipelines();

  // 1. Compute methodName.
  const methodName = useMemo(() => {
    if (node.info.nodeType === 'TRIGGER') return 'trigger';
    if (node.info.nodeType === 'FLOW' && Array.isArray(node.methods) && node.methods.length > 0) {
      return configuration?.method || node.methods[0].name;
    }
    // For UTILITY and other nodes, if configuration.method is provided, use it;
    // otherwise, use the first available method key.
    return configuration?.method || (node.methods ? Object.keys(node.methods)[0] : 'wait');
  }, [node.methods, configuration, node.info.nodeType]);

  // 2. Compute methodInfo with an explicit branch for UTILITY nodes.
  const methodInfo = useMemo(() => {
    if (node.info.nodeType === 'FLOW') {
      if (Array.isArray(node.methods) && node.methods.length > 0) {
        return node.methods[0];
      } else if (node.methods && typeof node.methods === 'object') {
        return node.methods[methodName];
      }
    }
    if (node.info.nodeType === 'TRIGGER') {
      if (Array.isArray(node.methods)) {
        return node.methods.find((m: any) => m.name === 'trigger') || node.methods[0];
      } else if (typeof node.methods === 'object') {
        const methods = Object.values(node.methods);
        return methods.find((m: any) => m.name === 'trigger') || methods[0];
      }
    }
    if (node.info.nodeType === 'UTILITY') {
      // For utility nodes, simply return the first method.
      if (Array.isArray(node.methods) && node.methods.length > 0) {
        return node.methods[0];
      } else if (node.methods && typeof node.methods === 'object') {
        return node.methods[Object.keys(node.methods)[0]];
      }
    }
    // Fallback for other node types.
    if (Array.isArray(node.methods)) {
      const index = configuration?.method
        ? node.methods.findIndex((m: any) => m.name === configuration.method)
        : 0;
      return node.methods[index];
    } else if (typeof node.methods === 'object') {
      return node.methods[configuration?.method || Object.keys(node.methods)[0]];
    }
    return undefined;
  }, [node.info.nodeType, node.methods, configuration?.method, methodName]);

  // 3. Compute flowParameters (for FLOW nodes).
  const flowParameters = useMemo(() => {
    if (node.info.nodeType === 'FLOW') {
      if (Array.isArray(node.methods) && node.methods.length > 0) {
        console.log("FLOW node detected (array). Using original config parameters:", node.methods[0]?.config?.parameters);
        return node.methods[0]?.config?.parameters || [];
      } else if (node.methods && typeof node.methods === 'object') {
        const methodObj = node.methods[methodName] as any;
        console.log("FLOW node detected (object). Using config parameters from key", methodName, ":", methodObj?.config?.parameters);
        return methodObj?.config?.parameters || [];
      }
    }
    // For non-FLOW nodes, use config parameters from methodInfo.
    return (methodInfo as any)?.config?.parameters || [];
  }, [node.info.nodeType, node.methods, methodName, methodInfo]);

  // 4. Compute effective parameters.
  const effectiveParameters = useMemo(() => {
    if (node.info.nodeType === 'FLOW') {
      return Object.values(flowParameters);
    } else if (node.info.nodeType === 'UTILITY') {
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
      // If topLevelParams exists as an object, convert it to an array.
      if (topLevelParams && typeof topLevelParams === 'object') {
        return Object.values(topLevelParams);
      }
      // Finally, if configParams exists as an object, convert it.
      if (configParams && typeof configParams === 'object') {
        return Object.values(configParams);
      }
      return [];
    }
    // For TRIGGER or INTEGRATION nodes.
    return (methodInfo as any)?.config?.parameters || [];
  }, [node.info.nodeType, flowParameters, methodInfo]);

  const hasParameters = useMemo(() => effectiveParameters.length > 0, [effectiveParameters]);

  // 5. Determine node type flags.
  const isIntegrationNode = useMemo(() => node.info.nodeType === 'INTEGRATION', [node.info.nodeType]);
  const isTriggerNode = useMemo(() => node.info.nodeType === 'TRIGGER', [node.info.nodeType]);
  const isFlowNode = useMemo(() => node.info.nodeType === 'FLOW', [node.info.nodeType]);

  const integrationOptions = useMemo(() => {
    if (!integrationsData?.data) return [];
    return integrationsData.data.map(integration => ({
      label: integration.name,
      value: integration.id,
    }));
  }, [integrationsData]);

  const pipelinesOptions = useMemo(() => {
    if (!pipelinesData?.data?.s) return [];
    return pipelinesData.data.s.map(pipeline => ({
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
        name: 'integrationId',
        type: 'select',
        label: 'Select Integration',
        tooltip: 'Select an integration for this node',
        required: true,
        options: integrationOptions,
        validation: {
          type: 'string',
          rules: [{
            type: 'regex',
            value: '.+',
            message: 'An integration must be selected',
          }],
        },
      });
    }

    // For TRIGGER, FLOW, and UTILITY nodes, use effectiveParameters.
    if (isTriggerNode || isFlowNode || node.info.nodeType === 'UTILITY') {
      console.log("Effective method parameters:", effectiveParameters);
      if (effectiveParameters.length > 0) {
        effectiveParameters.forEach((param: any) => {
          const field: FormFieldDefinition = {
            name: `parameters.${param.name}`,
            type: mapParameterTypeToFormType(param.schema?.type || 'string'),
            label: param.label || param.name,
            required: param.required,
            tooltip: param.description,
          };
          if (param.schema?.type === 'select' && param.schema?.options) {
            const options = param.schema.options.map((opt: any) => ({
              label: opt.label || opt,
              value: opt.value || opt,
            }));
            field.options = options;
            field.type = 'select';
            if (field.required) {
              field.validation = {
                type: 'string',
                rules: [{
                  type: 'regex',
                  value: '.+',
                  message: 'This field is required',
                }],
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
            type: param.type === 'number' ? 'number' : 'string',
            rules: [{
              type: 'regex',
              value: '.+',
              message: 'This field is required',
            }],
          };
        }
        if (param.type === 'select' && 'options' in param) {
          const options = (param as any).options?.map((opt: any) => ({
            label: opt.label || opt,
            value: opt.value || opt,
          })) || [];
          field.options = options;
        }
        fields.push(field);
      });
    }

    if (isTriggerNode) {
      const workflowField = fields.find(field => field.name === 'parameters.pipeline_name');
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
    node.info.nodeType
  ]);

  const handleFormSubmit = useCallback(async (data: any) => {
    try {
      console.log('[NodeConfigurationForm] Form data:', data);
      console.log('[NodeConfigurationForm] methodInfo:', methodInfo);
      console.log('[NodeConfigurationForm] Node type:', node.info.nodeType);
      console.log('[NodeConfigurationForm] methodName:', methodName);
      let method;
      let path = '';
      let operationId = '';
      let requestMapping = null;
      let responseMapping = null;
      if (node.info.nodeType === 'TRIGGER' || node.info.nodeType === 'FLOW') {
        method = methodName;
        console.log('[NodeConfigurationForm] Using method name for trigger/flow node:', method);
      } else if (node.info.nodeType === 'INTEGRATION') {
        method = methodName;
        const methodConfig = (methodInfo as any)?.config;
        console.log('[NodeConfigurationForm] Method config:', methodConfig);
        if (methodConfig) {
          path = methodConfig.path || '';
          operationId = methodConfig.operationId || '';
          requestMapping = methodConfig.requestMapping || null;
          responseMapping = methodConfig.responseMapping || null;
        }
        console.log('[NodeConfigurationForm] Using method name for integration node:', method);
        console.log('[NodeConfigurationForm] Path:', path);
        console.log('[NodeConfigurationForm] OperationId:', operationId);
        console.log('[NodeConfigurationForm] RequestMapping:', requestMapping);
        console.log('[NodeConfigurationForm] ResponseMapping:', responseMapping);
      } else {
        const opId = (methodInfo as any)?.config?.operationId;
        method = opId || methodName;
        console.log('[NodeConfigurationForm] Using operationId or method name:', method);
      }
      const config: NodeConfiguration = {
        method: method,
        parameters: data.parameters || {},
        integrationId: isIntegrationNode ? data.integrationId : undefined,
        path: path || configuration?.path || '',
        operationId: operationId || configuration?.operationId || '',
        requestMapping: requestMapping !== null ? requestMapping : configuration?.requestMapping,
        responseMapping: responseMapping !== null ? responseMapping : configuration?.responseMapping,
      };
      console.log('[NodeConfigurationForm] Submitting config:', config);
      try {
        console.log('[NodeConfigurationForm] Calling onSubmit with config:', JSON.stringify(config));
        await onSubmit(config);
        console.log('[NodeConfigurationForm] Submit successful');
      } catch (submitError) {
        console.error('[NodeConfigurationForm] Submit error:', submitError);
      }
    } catch (error) {
      console.error('[NodeConfigurationForm] Submit failed:', error);
    }
  }, [methodName, methodInfo, node.info.nodeType, configuration?.path, configuration?.operationId, configuration?.requestMapping, configuration?.responseMapping, onSubmit, isIntegrationNode]);

  // For nodes without parameters (excluding UTILITY), auto-submit.
  useEffect(() => {
    if (
      !hasParameters &&
      !isIntegrationNode &&
      !isTriggerNode &&
      !isFlowNode &&
      node.info.nodeType !== 'UTILITY'
    ) {
      console.log('[NodeConfigurationForm] Auto-submitting for node with no parameters');
      let method;
      if (node.info.nodeType === 'TRIGGER') {
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
      console.log('[NodeConfigurationForm] Auto-submitting config:', config);
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
    isFlowNode
  ]);

  // For nodes without parameters (excluding UTILITY), show a "no configuration" message.
  if (!hasParameters && !isIntegrationNode && !isTriggerNode && !isFlowNode && node.info.nodeType !== 'UTILITY') {
    return (
      <Box sx={{ p: 2, textAlign: 'center' }}>
        <Typography variant="body1" color="text.secondary">
          {t('nodes.noConfiguration')}
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
    if (methodInfo?.parameters) {
      Object.entries(methodInfo.parameters).forEach(([key, param]: [string, NodeParameter]) => {
        if (param.type === 'select' && 'options' in param) {
          const options = (param as any).options || [];
          if (!values.parameters[key] && options.length > 0) {
            values.parameters = {
              ...values.parameters,
              [key]: options[0].value || '',
            };
          }
        }
        if (param.required && !values.parameters[key]) {
          if (param.type === 'boolean') {
            values.parameters = {
              ...values.parameters,
              [key]: false,
            };
          } else if (param.type === 'number') {
            values.parameters = {
              ...values.parameters,
              [key]: 0,
            };
          } else if (param.type !== 'select') {
            values.parameters = {
              ...values.parameters,
              [key]: '',
            };
          }
        }
      });
    }
    return values;
  }, [configuration?.parameters, configuration?.integrationId, isIntegrationNode, methodInfo, integrationOptions]);

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

NodeConfigurationForm.displayName = 'NodeConfigurationForm';

export default NodeConfigurationForm;
