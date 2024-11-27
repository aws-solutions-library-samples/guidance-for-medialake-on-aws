export interface PipelineExecution {
    execution_id: string;
    pipeline_name: string;
    status: 'SUCCEEDED' | 'FAILED' | 'RUNNING' | 'TIMED_OUT' | 'ABORTED';
    state_machine_arn: string;
    start_time: string;
    end_time?: string;
    duration_seconds: string;
    last_updated: string;
    ttl: string;
    execution_arn: string;
}

export interface SearchMetadata {
    totalResults: number;
    page: number;
    pageSize: number;
}

export interface PipelineExecutionsResponse {
    status: string;
    message: string;
    data: {
        searchMetadata: SearchMetadata;
        executions: PipelineExecution[];
    };
}

export interface PipelineExecutionFilters {
    status?: string;
    startDate?: string;
    endDate?: string;
    sortBy?: string;
    sortOrder?: 'asc' | 'desc';
}
