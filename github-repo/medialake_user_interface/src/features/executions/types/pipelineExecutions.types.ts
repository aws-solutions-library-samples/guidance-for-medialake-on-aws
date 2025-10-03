export interface PipelineExecution {
  execution_id: string;
  start_time: string; // epoch timestamp as string
  start_time_iso: string;
  end_time?: string; // epoch timestamp as string
  end_time_iso?: string;
  pipeline_name: string;
  status: string;
  state_machine_arn: string;
  execution_arn: string;
  last_updated: string;
  ttl: string;
  pipeline_id?: string;
  duration_seconds?: string;
  error_message?: string;
  inventory_id?: string;
  object_key_name?: string;
  pipeline_trace_id?: string;
  step_name?: string;
  step_status?: string;
  step_result?: string;
  error?: string;
  cause?: string | object;
  metadata?: object;
  aws_account_id?: string;
  machine_region?: string;
  dsa_type?: string;

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
  search?: string;
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
