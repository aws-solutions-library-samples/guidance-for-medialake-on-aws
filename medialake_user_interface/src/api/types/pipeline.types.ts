export interface StepFunctionDefinition {
    Comment?: string;
    StartAt: string;
    States: {
        [key: string]: {
            Type: string;
            Resource?: string;
            Next?: string;
            End?: boolean;
            Catch?: Array<{
                ErrorEquals: string[];
                Next: string;
            }>;
            Parameters?: Record<string, any>;
            ResultPath?: string;
            InputPath?: string;
            OutputPath?: string;
        };
    };
}

export interface PipelineDetails {
    pipelineId: string;
    name: string;
    type: string;
    createdAt: string;
    updatedAt: string;
    status: 'ACTIVE' | 'INACTIVE';
    definition: StepFunctionDefinition;
    roleArn: string;
    tags?: Record<string, string>;
    description?: string;
}

export interface PipelineMetrics {
    executionsStarted: number;
    executionsSucceeded: number;
    executionsFailed: number;
    executionsTimedOut: number;
    averageExecutionDuration: number;
}

export interface PipelineDetailsResponse {
    status: string;
    message: string;
    data: {
        details: PipelineDetails;
        metrics: PipelineMetrics;
    };
}
