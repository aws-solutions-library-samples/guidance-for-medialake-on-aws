export interface Pipeline {
    id: string;
    name: string;
    type: 'Ingest Triggered' | string;
    system: boolean;
    description?: string;
    configuration?: PipelineConfiguration;
    createdAt: string;
    updatedAt: string;
    queueUrl: string;
    queueArn: string;
    stateMachineArn: string;
    sfnRoleArn: string;
    triggerLambdaArn: string;
    dependentResources: [string, string | { rule_name: string; eventbus_name: string }][];
    deploymentStatus?: 'CREATING' | 'DEPLOYED' | 'FAILED' | string;
    executionArn?: string;
    active?: boolean; // New field to track if the pipeline is active
    definition: {
        nodes: PipelineNode[];
        edges: PipelineEdge[];
        viewport: {
            x: string;
            y: string;
            zoom: string;
        };
    };
}

export interface PipelineConfiguration {
    nodes: PipelineNode[];
    edges: PipelineEdge[];
    settings: PipelineSettings;
}

export interface PipelineNode {
    id: string;
    type: string;
    position: {
        x: number | string;
        y: number | string;
    };
    data: {
        icon?: {
            props: {
                size: string | number;
            };
        };
        inputTypes: string[];
        outputTypes: string[];
        id?: string;
        label: string;
        type: string;
        description?: string;
        seconds?: string;
        cause?: string;
        width?: string;
        height?: string;
        configuration?: any;
    };
    width: string;
    height: string;
    positionAbsolute?: {
        x: number | string;
        y: number | string;
    };
    dragging?: boolean;
    selected?: boolean;
}

export interface PipelineEdge {
    source: string;
    id: string;
    type: string;
    data: {
        text: string;
        condition?: {
            variable: string;
            equals?: string;
            not_equals?: string[];
        };
    };
    target: string;
}

export interface PipelineSettings {
    autoStart: boolean;
    retryAttempts: number;
    timeout: number;
}

export type PipelineStatus = 'active' | 'inactive' | 'running' | 'failed' | 'completed';

export interface PipelineRun {
    id: string;
    pipelineId: string;
    status: PipelineStatus;
    startTime: string;
    endTime?: string;
    logs: string[];
}

export interface CreatePipelineDto {
    name: string;
    description?: string;
    configuration: PipelineConfiguration;
    active?: boolean; // New optional field
}

export interface UpdatePipelineDto {
    name?: string;
    description?: string;
    configuration?: PipelineConfiguration;
    active?: boolean; // New optional field
}

export interface SearchMetadata {
    totalResults: number;
    pageSize: number;
    nextToken: string | null;
}

export interface PipelinesResponse {
    status: string;
    message: string;
    data: {
        searchMetadata: SearchMetadata;
        s: Pipeline[];
    };
}

export interface PipelineError {
    message: string;
    status?: number;
    code?: string;
}

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
}

export interface NodeAuth {
    authMethod: string;
    authConfig: {
        type: string;
        parameters: {
            name: string;
            description?: string;
            type: string;
            in: string;
        }
    }
}

export interface Node {
    info: NodeInfo;
    auth: NodeAuth;
} 