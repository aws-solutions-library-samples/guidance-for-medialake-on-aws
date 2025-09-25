export interface PipelineExecution {
  execution_id: string;
  pipeline_id: string;
  pipeline_name: string;
  status: string;
  start_time: string;
  end_time?: string;
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
  sortOrder?: "asc" | "desc";
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
