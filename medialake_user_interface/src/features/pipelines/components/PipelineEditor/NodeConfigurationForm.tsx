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

    const methodName = useMemo(() => {
        // For trigger nodes, always use "trigger" as the method name
        if (node.info.nodeType === 'TRIGGER') {
            return 'trigger';
        }
        // For other nodes, use the method from existing configuration if available
        return configuration?.method || Object.keys(node.methods)[0];
    }, [node.methods, configuration, node.info.nodeType]);

    const methodInfo = useMemo(() => {
        // For trigger nodes, we need to find the method in the methods array or object
        if (node.info.nodeType === 'TRIGGER') {
            let method;

            // Handle both array and object formats
            if (Array.isArray(node.methods)) {
                method = node.methods.find((m: any) => m.name === methodName);
            } else if (typeof node.methods === 'object') {
                // Try to find the method by name in the object
                const methods = Object.values(node.methods);
                method = methods.find((m: any) => m.name === methodName);

                // If not found, just use the first method (likely the trigger method)
                if (!method && methods.length > 0) {
                    method = methods[0];
                }
            }

            return method;
        }

        // For other nodes, we can use the method name as the key
        return node.methods[methodName];
    }, [node.methods, methodName, node.info.nodeType]);

    const isIntegrationNode = useMemo(() =>
        node.info.nodeType === 'INTEGRATION',
        [node.info.nodeType]
    );

    const isTriggerNode = useMemo(() =>
        node.info.nodeType === 'TRIGGER',
        [node.info.nodeType]
    );

    const isFlowNode = useMemo(() =>
        node.info.nodeType === 'FLOW',
        [node.info.nodeType]
    );

    const hasParameters = useMemo(() => {
        if (node.info.nodeType === 'TRIGGER' || node.info.nodeType === 'FLOW') {
            // For trigger and flow nodes, check if there are parameters in the config
            const parameters = (methodInfo as any)?.config?.parameters || [];
            return parameters.length > 0;
        } else {
            // For other nodes, check the parameters object
            const paramCount = Object.keys(methodInfo?.parameters || {}).length;
            return paramCount > 0;
        }
    }, [methodInfo, node.info.nodeType]);

    const integrationOptions = useMemo(() => {
        if (!integrationsData?.data) return [];
        return integrationsData.data.map(integration => ({
            label: integration.name,
            value: integration.id
        }));
    }, [integrationsData]);

    const pipelinesOptions = useMemo(() => {
        if (!pipelinesData?.data?.s) return [];
        return pipelinesData.data?.s.map(pipeline => ({
            label: pipeline.name,
            value: pipeline.id
        }));
    }, [pipelinesData]);

    const formDefinition = useMemo<FormDefinition>(() => {
        const fields: FormFieldDefinition[] = [];

        // Add integration selection field
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
                    rules: [
                        {
                            type: 'regex',
                            value: '.+', // Matches any non-empty string
                            message: 'An integration must be selected'
                        }
                    ]
                }
            });
        }

        // Add method parameters

        // Handle different parameter structures based on node type
        if (isTriggerNode || isFlowNode) {
            // For trigger and flow nodes, parameters are in a different format
            // They are in an array format with config.parameters
            const parameters = (methodInfo as any)?.config?.parameters || [];

            if (parameters.length > 0) {
                parameters.forEach((param: any) => {
                    const field: FormFieldDefinition = {
                        name: `parameters.${param.name}`,
                        type: mapParameterTypeToFormType(param.schema?.type || 'string'),
                        label: param.label || param.name,
                        required: param.required,
                        tooltip: param.description
                    };

                    // Handle select fields
                    if (param.schema?.type === 'select' && param.schema?.options) {
                        const options = param.schema.options.map((opt: any) => ({
                            label: opt.label || opt,
                            value: opt.value || opt,
                        }));

                        field.options = options;
                        field.type = 'select';

                        // Add validation for required select fields
                        if (field.required) {
                            field.validation = {
                                type: 'string',
                                rules: [
                                    {
                                        type: 'regex',
                                        value: '.+', // Matches any non-empty string
                                        message: 'This field is required'
                                    }
                                ]
                            };
                        }
                    }

                    fields.push(field);
                });
            }
        } else if (methodInfo?.parameters) {
            // For other nodes, parameters are in a key-value format
            Object.entries(methodInfo.parameters).forEach(([key, param]: [string, NodeParameter]) => {
                const field: FormFieldDefinition = {
                    name: `parameters.${key}`,
                    type: mapParameterTypeToFormType(param.type),
                    label: param.label || key,
                    required: param.required,
                    tooltip: param.description
                };

                // Add validation for all required fields
                if (param.required) {
                    field.validation = {
                        type: param.type === 'number' ? 'number' : 'string',
                        rules: [
                            {
                                type: 'regex',
                                value: '.+', // Matches any non-empty string
                                message: 'This field is required'
                            }
                        ]
                    };
                }

                // Handle select fields
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

        // Process trigger node fields after all fields are added
        if (isTriggerNode) {
            const workflowField = fields.find(field => field.name === 'parameters.pipeline_name');
            if (workflowField) {
                Object.assign(workflowField, {
                    options: pipelinesOptions
                });
            }
        }

        return {
            id: `node-config-${node.nodeId}-form`,
            name: node.info.title,
            description: node.info.description,
            fields,
        };
    }, [node.nodeId, node.info.title, node.info.description, methodInfo, isIntegrationNode, isTriggerNode, integrationOptions, pipelinesOptions]);

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
                // For trigger and flow nodes, use the method name directly
                method = methodName;
                console.log('[NodeConfigurationForm] Using method name for trigger/flow node:', method);
            } else if (node.info.nodeType === 'INTEGRATION') {
                // For integration nodes, use the method name (post, get, etc.)
                method = methodName;

                // Get the path, operationId, requestMapping, and responseMapping from the methodInfo
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
                // For other nodes, use the operationId if available
                const operationId = (methodInfo as any)?.config?.operationId;
                method = operationId || methodName;
                console.log('[NodeConfigurationForm] Using operationId or method name:', method);
            }

            const config: NodeConfiguration = {
                method: method,
                parameters: data.parameters || {},
                integrationId: isIntegrationNode ? data.integrationId : undefined,
                path: path || configuration?.path || '',
                operationId: operationId || configuration?.operationId || '',
                requestMapping: requestMapping !== null ? requestMapping : configuration?.requestMapping,
                responseMapping: responseMapping !== null ? responseMapping : configuration?.responseMapping
            };
            console.log('[NodeConfigurationForm] Submitting config:', config);

            // Ensure we're not throwing any errors during submission
            try {
                console.log('[NodeConfigurationForm] Calling onSubmit with config:', JSON.stringify(config));
                await onSubmit(config);
                console.log('[NodeConfigurationForm] Submit successful');
            } catch (submitError) {
                console.error('[NodeConfigurationForm] Submit error:', submitError);
                // Don't rethrow to prevent blocking the UI
            }
        } catch (error) {
            console.error('[NodeConfigurationForm] Submit failed:', error);
            // Don't rethrow to prevent blocking the UI
        }
    }, [methodName, methodInfo, node.info.nodeType, configuration?.path, configuration?.operationId, configuration?.requestMapping, configuration?.responseMapping, onSubmit, isIntegrationNode]);

    // Auto-submit when there are no parameters and it's not an integration node or trigger node
    useEffect(() => {
        if (!hasParameters && !isIntegrationNode && !isTriggerNode && !isFlowNode) {
            console.log('[NodeConfigurationForm] Auto-submitting for node with no parameters');

            // Set method based on node type
            let method;
            if (node.info.nodeType === 'TRIGGER') {
                // For trigger nodes, use the method name directly
                method = methodName;
            } else {
                // For other nodes, use the operationId if available
                const operationId = (methodInfo as any)?.config?.operationId;
                method = operationId || methodName;
            }

            const config: NodeConfiguration = {
                method: method,
                parameters: {},
                path: configuration?.path,
                operationId: configuration?.operationId,
                requestMapping: configuration?.requestMapping,
                responseMapping: configuration?.responseMapping
            };
            console.log('[NodeConfigurationForm] Auto-submitting config:', config);
            onSubmit(config).catch(console.error);
        }
    }, [hasParameters, methodName, methodInfo, node.info.nodeType, configuration?.path, configuration?.operationId, configuration?.requestMapping, configuration?.responseMapping, onSubmit, isIntegrationNode, isTriggerNode]);

    if (!hasParameters && !isIntegrationNode && !isTriggerNode && !isFlowNode) {
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
            integrationId: isIntegrationNode ? configuration?.integrationId : undefined
        };

        // For integration nodes, set a default integration if none is selected
        if (isIntegrationNode && !values.integrationId && integrationOptions.length > 0) {
            values.integrationId = integrationOptions[0].value;
        }

        // Set default values for any select fields that don't have a value
        if (methodInfo?.parameters) {
            Object.entries(methodInfo.parameters).forEach(([key, param]: [string, NodeParameter]) => {
                if (param.type === 'select' && 'options' in param) {
                    const options = (param as any).options || [];
                    // If no value exists for this parameter and options are available
                    if (!values.parameters[key] && options.length > 0) {
                        // Ensure we're working with the correct type
                        values.parameters = {
                            ...values.parameters,
                            [key]: options[0].value || ''
                        };
                    }
                }

                // Set default values for required fields to prevent validation errors
                if (param.required && !values.parameters[key]) {
                    if (param.type === 'boolean') {
                        values.parameters = {
                            ...values.parameters,
                            [key]: false
                        };
                    } else if (param.type === 'number') {
                        values.parameters = {
                            ...values.parameters,
                            [key]: 0
                        };
                    } else if (param.type !== 'select') { // Skip select as it's handled above
                        values.parameters = {
                            ...values.parameters,
                            [key]: ''
                        };
                    }
                }
            });
        }

        return values;
    }, [configuration?.parameters, configuration?.integrationId, isIntegrationNode]);

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
