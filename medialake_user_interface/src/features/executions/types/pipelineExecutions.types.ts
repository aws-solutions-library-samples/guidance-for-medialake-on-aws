export interface PipelineExecution {
    execution_id: string;
    start_time: string;  // epoch timestamp as string
    start_time_iso: string;
    end_time?: string;   // epoch timestamp as string
    end_time_iso?: string;
    pipeline_name: string;
    status: string;
    state_machine_arn: string;
    execution_arn: string;
    last_updated: string;
    ttl: string;
    pipeline_id: string;
    duration_seconds?: string;
    error_message?: string;
    steps?: Array<{
        step_id: string;
        status: string;
        start_time: string;
        end_time?: string;
        error_message?: string;
    }>;
}

export interface PipelineExecutionFilters {
    status?: string;
    startDate?: string;
    endDate?: string;
    sortBy?: string;
    sortOrder?: 'asc' | 'desc';
}

export interface PipelineExecutionsSearchMetadata {
    totalResults: number;
    pageSize: number;
    nextToken?: string;
}

export interface PipelineExecutionsResponse {
    status: string;
    message: string;
    data: {
        searchMetadata: PipelineExecutionsSearchMetadata;
        executions: PipelineExecution[];
    };
}