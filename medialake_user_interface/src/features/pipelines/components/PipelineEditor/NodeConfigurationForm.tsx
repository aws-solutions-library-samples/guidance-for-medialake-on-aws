import React, { useEffect, useMemo, useCallback } from 'react';
import { Box, Typography } from '@mui/material';
import { useTranslation } from 'react-i18next';
import { DynamicForm } from '../../../../forms/components/DynamicForm';
import { FormDefinition, FormFieldDefinition } from '../../../../forms/types';
import { NodeConfiguration, Node as NodeType, NodeParameter } from '@/features/pipelines/types';

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

export const NodeConfigurationForm = React.memo(({
    node,
    configuration,
    onSubmit,
    onCancel,
}) => {
    const { t } = useTranslation();

    const methodName = useMemo(() => Object.keys(node.methods)[0], [node.methods]);
    const methodInfo = useMemo(() => node.methods[methodName], [node.methods, methodName]);
    const hasParameters = useMemo(
        () => Object.keys(methodInfo?.parameters || {}).length > 0,
        [methodInfo]
    );

    const formDefinition = useMemo<FormDefinition>(() => {
        console.log('[NodeConfigurationForm] Creating form definition');
        const fields: FormFieldDefinition[] = [];

        if (methodInfo?.parameters) {
            Object.entries(methodInfo.parameters).forEach(([key, param]: [string, NodeParameter]) => {
                const field: FormFieldDefinition = {
                    name: `parameters.${key}`,
                    type: mapParameterTypeToFormType(param.type),
                    label: param.name || key,
                    required: param.required,
                    tooltip: param.description,
                    useDirectLabels: true,
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
            useDirectLabels: true,
        };
    }, [node.nodeId, node.info.title, node.info.description, methodInfo]);

    const handleFormSubmit = useCallback(async (data: any) => {
        try {
            const config: NodeConfiguration = {
                method: methodName,
                parameters: data.parameters || {},
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
    }, [methodName, configuration?.path, configuration?.operationId, configuration?.inputMapping, configuration?.outputMapping, onSubmit]);

    // Auto-submit when there are no parameters
    useEffect(() => {
        if (!hasParameters) {
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
    }, [hasParameters, methodName, configuration?.path, configuration?.operationId, configuration?.inputMapping, configuration?.outputMapping, onSubmit]);

    if (!hasParameters) {
        return (
            <Box sx={{ p: 2, textAlign: 'center' }}>
                <Typography variant="body1" color="text.secondary">
                    No configuration or mapping needed
                </Typography>
            </Box>
        );
    }

    return (
        <Box>
            <DynamicForm
                definition={formDefinition}
                defaultValues={{ 
                    parameters: configuration?.parameters || {} 
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
