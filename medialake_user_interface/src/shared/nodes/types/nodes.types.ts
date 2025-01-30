export interface NodeInfo {
    enabled: boolean;
    categories: string[];
    updatedAt: string;
    nodeType: string;
    createdAt: string;
    iconUrl: string;
    description: string;
    tags: string[];
    title: string;
    inputTypes?: string[];
    outputTypes?: string[];
}

export interface NodeAuth {
    authMethod: string;
    authConfig: {
        type: string;
        parameters: {
            type: string;
            name: string;
            in: string;
        };
    };
}

export interface NodeMethodParameter {
    name: string;
    type: 'string' | 'number' | 'boolean' | 'array';
    description: string;
    required: boolean;
    defaultValue?: any;
}

export interface NodeMethod {
    name: string;
    description: string;
    parameters: NodeMethodParameter[];
}

export interface Node {
    info: NodeInfo;
    auth: NodeAuth;
    nodeId?: string;
    methods: NodeMethod[];
}

export interface NodesResponse {
    status: string;
    message: string;
    data?: Node[];
}

export interface NodesError {
    status: string;
    message: string;
}
