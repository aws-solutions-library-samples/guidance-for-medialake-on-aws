import React, { useMemo, useState } from 'react';
import { Node } from 'reactflow';
import { Box, Button, Stack } from '@mui/material';
import { Node as NodeType } from '@/shared/nodes/types/nodes.types';
import { DynamicForm } from '@/forms/components/DynamicForm';
import { FormDefinition, FormFieldDefinition } from '@/forms/types';

interface NodeConfigurationFormProps {
    node: Node;
    nodeDetails: NodeType;
    onSave: (configuration: any) => void;
    onCancel: () => void;
}

const mapNodeTypeToFormType = (type: string): FormFieldDefinition['type'] => {
    switch (type) {
        case 'number':
            return 'number';
        case 'boolean':
            return 'switch';
        case 'array':
            return 'multiselect';
        default:
            return 'text';
    }
};

const mapNodeTypeToValidationType = (type: string): "string" | "number" | "boolean" | "array" => {
    switch (type) {
        case 'number':
            return 'number';
        case 'boolean':
            return 'boolean';
        case 'array':
            return 'array';
        default:
            return 'string';
    }
};

export const NodeConfigurationForm: React.FC<NodeConfigurationFormProps> = ({
    node,
    nodeDetails,
    onSave,
    onCancel,
}) => {
    const [selectedMethod, setSelectedMethod] = useState<string>(node.data.configuration?.method || '');

    const formDefinition: FormDefinition = useMemo(() => {
        const selectedMethodDetails = nodeDetails.methods?.find(m => m.name === selectedMethod);

        return {
            id: `node-config-${node.id}`,
            name: `Configure ${nodeDetails.info.title}`,
            description: nodeDetails.info.description,
            translationPrefix: 'nodes.configuration',
            fields: [
                {
                    id: `method-${node.id}`,
                    name: 'method',
                    type: 'select' as const,
                    label: 'Method',
                    tooltip: 'Select the method to use for this node',
                    required: true,
                    options: nodeDetails.methods?.map(method => ({
                        label: `${method.name} - ${method.description}`,
                        value: method.name
                    })) || [],
                    defaultValue: selectedMethod,
                    onChange: (value: string) => {
                        setSelectedMethod(value);
                    }
                },
                // Add fields based on the selected method's parameters
                ...(selectedMethodDetails?.parameters || []).map(param => ({
                    id: `${node.id}-${param.name}`,
                    name: `params.${param.name}`,
                    type: mapNodeTypeToFormType(param.type),
                    label: param.name,
                    tooltip: param.description,
                    required: param.required,
                    validation: {
                        type: mapNodeTypeToValidationType(param.type),
                        rules: []
                    },
                    defaultValue: node.data.configuration?.params?.[param.name]
                }))
            ]
        };
    }, [node, nodeDetails, selectedMethod]);

    const handleSubmit = async (data: any) => {
        const configuration = {
            method: data.method,
            params: Object.entries(data.params || {}).reduce((acc, [key, value]) => ({
                ...acc,
                [key]: value
            }), {})
        };
        onSave(configuration);
    };

    return (
        <Box sx={{ p: 2 }}>
            <DynamicForm
                definition={formDefinition}
                onSubmit={handleSubmit}
                onCancel={onCancel}
                defaultValues={node.data.configuration ? {
                    method: node.data.configuration.method,
                    params: node.data.configuration.params
                } : undefined}
            />
        </Box>
    );
};

export default NodeConfigurationForm; 
