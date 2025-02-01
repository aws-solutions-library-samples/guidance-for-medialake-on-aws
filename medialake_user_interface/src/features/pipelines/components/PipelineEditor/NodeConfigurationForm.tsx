import React, { useEffect, useMemo } from 'react';
import { DynamicForm } from '../../../../forms/components/DynamicForm';
import { FormDefinition, FormFieldDefinition } from '../../../../forms/types';
import { NodeConfiguration, Node as NodeType, NodeParameter } from '@/features/pipelines/types';
import { Box, Typography } from '@mui/material';

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

export const NodeConfigurationForm: React.FC<NodeConfigurationFormProps> = ({
    node,
    configuration,
    onSubmit,
    onCancel,
}) => {
    // Get the first method
    const methodName = Object.keys(node.methods)[0];
    const methodInfo = node.methods[methodName];
    const hasParameters = Object.keys(methodInfo?.parameters || {}).length > 0;

    // Auto-submit when there are no parameters
    useEffect(() => {
        if (!hasParameters) {
            const config: NodeConfiguration = {
                method: methodName,
                parameters: {},
                path: configuration?.path,
                operationId: configuration?.operationId,
            };
            onSubmit(config);
        }
    }, [hasParameters, methodName, configuration?.path, configuration?.operationId, onSubmit]);

    // Create form definition based on node info
    const formDefinition = useMemo<FormDefinition>(() => {
        const fields: FormFieldDefinition[] = [];

        if (methodInfo?.parameters) {
            Object.entries(methodInfo.parameters).forEach(([key, param]: [string, NodeParameter]) => {
                const field: FormFieldDefinition = {
                    name: `parameters.${key}`,
                    type: mapParameterTypeToFormType(param.type),
                    label: param.name,
                    required: param.required,
                    tooltip: param.description,
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
            id: `node-config-${node.nodeId}`,
            name: `Configure ${node.info.title}`,
            description: node.info.description,
            fields,
            translationPrefix: 'nodeConfiguration',
        };
    }, [node, methodInfo]);

    // Handle form submission
    const handleFormSubmit = async (data: any) => {
        const config: NodeConfiguration = {
            method: methodName,
            parameters: data.parameters || {},
            path: configuration?.path,
            operationId: configuration?.operationId,
        };
        await onSubmit(config);
    };

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
        <DynamicForm
            definition={formDefinition}
            defaultValues={{ parameters: configuration?.parameters || {} }}
            onSubmit={handleFormSubmit}
            onCancel={onCancel}
        />
    );
};

export default NodeConfigurationForm;
