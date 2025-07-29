export interface ExecutionDetails {
  executionArn: string;
  stateMachineArn: string;
  name: string;
  status: "RUNNING" | "SUCCEEDED" | "FAILED" | "TIMED_OUT" | "ABORTED";
  startDate: string;
  stopDate?: string;
  input: string;
  inputDetails: {
    included: boolean;
  };
  output?: string;
  outputDetails?: {
    included: boolean;
  };
  traceHeader?: string;
  error?: string;
  cause?: string;
}

export interface ExecutionHistoryEvent {
  timestamp: string;
  type: string;
  id: number;
  previousEventId?: number;
  stateEnteredEventDetails?: {
    name: string;
    input: string;
  };
  stateExitedEventDetails?: {
    name: string;
    output: string;
  };
  taskScheduledEventDetails?: {
    resourceType: string;
    resource: string;
    parameters: string;
  };
  taskStartedEventDetails?: {
    resource: string;
  };
  taskSucceededEventDetails?: {
    output: string;
    resource: string;
  };
  taskFailedEventDetails?: {
    error: string;
    cause: string;
    resource: string;
  };
}

export interface ExecutionDetailsResponse {
  status: string;
  message: string;
  data: {
    execution: ExecutionDetails;
    history: ExecutionHistoryEvent[];
  };
}
