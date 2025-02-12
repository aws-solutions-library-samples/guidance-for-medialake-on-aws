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

    const methodName = useMemo(() => Object.keys(node.methods)[0], [node.methods]);
    const methodInfo = useMemo(() => node.methods[methodName], [node.methods, methodName]);

    const hasParameters = useMemo(
        () => Object.keys(methodInfo?.parameters || {}).length > 0,
        [methodInfo]
    );

    const isIntegrationNode = useMemo(() =>
        node.info.nodeType === 'INTEGRATION',
        [node.info.nodeType]
    );

    const isTriggerNode = useMemo(() =>
        node.info.nodeType === 'TRIGGER',
        [node.info.nodeType]
    );

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
                options: integrationOptions
            });
        }

        // Add method parameters
        if (methodInfo?.parameters) {
            // console.log(methodInfo)
            Object.entries(methodInfo.parameters).forEach(([key, param]: [string, NodeParameter]) => {

                const field: FormFieldDefinition = {
                    name: `parameters.${key}`,
                    type: mapParameterTypeToFormType(param.type),
                    label: param.label || key,
                    required: param.required,
                    tooltip: param.description
                };

                // In formDefinition creation:
                if (param.type === 'select' && 'options' in param) {
                    const options = (param as any).options?.map((opt: any) => ({
                        label: opt.label || opt,
                        value: opt.value || opt,
                    })) || [];

                    field.options = options;

                    // Set default value to first option if no value is provided
                    if (!configuration?.parameters?.[key] && options.length > 0) {
                        if (!field.defaultValue) {
                            field.defaultValue = options[0].value;
                        }
                    }

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

        // Process trigger node fields after all fields are added
        if (isTriggerNode) {
            const workflowField = fields.find(field => field.name === 'parameters.pipeline_name');
            if (workflowField) {
                Object.assign(workflowField, {
                    // type: workflowField.type,
                    // label: workflowField.label,
                    // tooltip: 'Select a pipeline for this node',
                    // required: true,
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
    }, [node.nodeId, node.info.title, node.info.description, methodInfo, isIntegrationNode, integrationOptions]);


    const handleFormSubmit = useCallback(async (data: any) => {
        try {
            console.log('[NodeConfigurationForm] Form data:', data);
            const config: NodeConfiguration = {
                method: methodName,
                parameters: data.parameters || {},
                integrationId: isIntegrationNode ? data.integrationId : undefined,
                path: configuration?.path,
                operationId: configuration?.operationId,
                requestMapping: configuration?.requestMapping,
                responseMapping: configuration?.responseMapping
            };
            console.log('[NodeConfigurationForm] Submitting config:', config);
            await onSubmit(config);
        } catch (error) {
            console.error('[NodeConfigurationForm] Submit failed:', error);
            throw error;
        }
    }, [methodName, configuration?.path, configuration?.operationId, configuration?.requestMapping, configuration?.responseMapping, onSubmit, isIntegrationNode]);

    // Auto-submit when there are no parameters and it's not an integration node
    useEffect(() => {
        if (!hasParameters && !isIntegrationNode) {
            const config: NodeConfiguration = {
                method: methodName,
                parameters: {},
                path: configuration?.path,
                operationId: configuration?.operationId,
                requestMapping: configuration?.requestMapping,
                responseMapping: configuration?.responseMapping
            };
            onSubmit(config).catch(console.error);
        }
    }, [hasParameters, methodName, configuration?.path, configuration?.operationId, configuration?.requestMapping, configuration?.responseMapping, onSubmit, isIntegrationNode]);

    if (!hasParameters && !isIntegrationNode) {
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
            });
        }

        return values;
    }, [configuration?.parameters, configuration?.integrationId, isIntegrationNode, methodInfo]);

    // console.log('[NodeConfigurationForm] Default values:', formDefaultValues);
    console.log(formDefinition)
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
