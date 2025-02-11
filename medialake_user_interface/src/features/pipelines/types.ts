export interface NodeParameter {
    name: string;
    label: string;
    type: 'text' | 'number' | 'boolean' | 'select';
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
