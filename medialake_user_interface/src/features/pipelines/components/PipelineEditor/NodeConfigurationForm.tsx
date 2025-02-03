import React, { useEffect, useMemo, useCallback } from 'react';
import { Box, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { DynamicForm } from '../../../../forms/components/DynamicForm';
import { FormDefinition, FormFieldDefinition } from '../../../../forms/types';
import { NodeConfiguration, Node as NodeType, NodeParameter } from '@/features/pipelines/types';
import { useGetIntegrations } from '@/features/settings/integrations/api/integrations.controller';

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

    const integrationOptions = useMemo(() => {
        if (!integrationsData?.data) return [];
        return integrationsData.data.map(integration => ({
            label: integration.name,
            value: integration.id
        }));
    }, [integrationsData]);

    const formDefinition = useMemo<FormDefinition>(() => {
        console.log('[NodeConfigurationForm] Creating form definition');
        const fields: FormFieldDefinition[] = [];

        // Add integration selection field for INTEGRATION nodes
        if (isIntegrationNode) {
            fields.push({
                name: 'integrationId',
                type: 'select',
                label: t('nodes.integration.select'),
                tooltip: t('nodes.integration.selectTooltip'),
                required: true,
                options: integrationOptions
            });
        }

        if (methodInfo?.parameters) {
            Object.entries(methodInfo.parameters).forEach(([key, param]: [string, NodeParameter]) => {
                const field: FormFieldDefinition = {
                    name: `parameters.${key}`,
                    type: mapParameterTypeToFormType(param.type),
                    label: param.name || key,
                    required: param.required,
                    tooltip: param.description
                };

                if (param.type === 'select' && 'options' in param) {
                    field.options = (param as any).options?.map((opt: any) => ({
                        label: opt.label || opt,
                        value: opt.value || opt,
                    }));
                }

                fields.push(field);
            });
        }

        return {
            id: `node-config-${node.nodeId}-form`,
            name: node.info.title,
            description: node.info.description,
            fields,
        };
    }, [node.nodeId, node.info.title, node.info.description, methodInfo, isIntegrationNode, integrationOptions, t]);

    const handleFormSubmit = useCallback(async (data: any) => {
        try {
            const config: NodeConfiguration = {
                method: methodName,
                parameters: data.parameters || {},
                integrationId: isIntegrationNode ? data.integrationId : undefined,
                path: configuration?.path,
                operationId: configuration?.operationId,
                inputMapping: configuration?.inputMapping,
                outputMapping: configuration?.outputMapping
            };
            await onSubmit(config);
        } catch (error) {
            console.error('[NodeConfigurationForm] Submit failed:', error);
            throw error;
        }
    }, [methodName, configuration?.path, configuration?.operationId, configuration?.inputMapping, configuration?.outputMapping, onSubmit, isIntegrationNode]);

    // Auto-submit when there are no parameters and it's not an integration node
    useEffect(() => {
        if (!hasParameters && !isIntegrationNode) {
            const config: NodeConfiguration = {
                method: methodName,
                parameters: {},
                path: configuration?.path,
                operationId: configuration?.operationId,
                inputMapping: configuration?.inputMapping,
                outputMapping: configuration?.outputMapping
            };
            onSubmit(config).catch(console.error);
        }
    }, [hasParameters, methodName, configuration?.path, configuration?.operationId, configuration?.inputMapping, configuration?.outputMapping, onSubmit, isIntegrationNode]);

    if (!hasParameters && !isIntegrationNode) {
        return (
            <Box sx={{ p: 2, textAlign: 'center' }}>
                <Typography variant="body1" color="text.secondary">
                    {t('nodes.noConfiguration')}
                </Typography>
            </Box>
        );
    }

    return (
        <Box>
            {node.info.title && (
                <Typography variant="h6" sx={{ mb: 3 }}>
                    {node.info.title}
                </Typography>
            )}
            <DynamicForm
                definition={formDefinition}
                defaultValues={{ 
                    parameters: configuration?.parameters || {},
                    integrationId: configuration?.integrationId
                }}
                onSubmit={handleFormSubmit}
                onCancel={onCancel}
                showButtons={true}
            />
        </Box>
    );
});

NodeConfigurationForm.displayName = 'NodeConfigurationForm';

export default NodeConfigurationForm;
