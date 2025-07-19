export interface Pipeline {
  id: string;
  name: string;
  system: boolean;
  type: string;
  createdAt: string;
  updatedAt: string;
  eventBridgeRuleArn: string;
  roleArn: string;
  queueUrl: string;
  queueArn: string;
  stateMachineArn: string;
  triggerLambdaArn: string;
}

export interface PipelineFilters {
  status?: string;
  system?: string;
  startDate?: string;
  endDate?: string;
  sortBy?: string;
  sortOrder?: "asc" | "desc";
}

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
  status: "ACTIVE" | "INACTIVE";
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

// Pipelines

export interface PipelineNode {
  id: string;
  type: string;
  position: {
    x: number;
    y: number;
  };
  data: {
    id: string;
    type: string;
    label: string;
    icon: {
      key: null;
      ref: null;
      props: {
        size: number;
      };
      _owner: null;
    };
    inputTypes: string[];
    outputTypes: string[];
  };
  width: number;
  height: number;
  positionAbsolute: {
    x: number;
    y: number;
  };
  selected?: boolean;
  dragging?: boolean;
}

export interface PipelineEdge {
  source: string;
  sourceHandle: null;
  target: string;
  targetHandle: null;
  type: string;
  data: {
    text: string;
  };
  id: string;
}

export interface PipelineViewport {
  x: number;
  y: number;
  zoom: number;
}

export interface DeletePipelineRequest {
  id: string;
}

export interface CreatePipelineRequest {
  name: string;
  type: string;
  system: boolean;
  definition: {
    nodes: PipelineNode[];
    edges: PipelineEdge[];
    viewport: PipelineViewport;
  };
}

export interface PipelineResponse {
  id: string;
  status: string;
  message: string;
  data: {
    searchMetadata: PipelineSearchMetadata;
    s: Pipeline[]; // need to update the lambda to return pipelines instead of s
    error?: string;
    id?: string;
    name?: string;
    type?: string;
    createdAt?: string;
    updatedAt?: string;
    definition?: {
      nodes: PipelineNode[];
      edges: PipelineEdge[];
      viewport: PipelineViewport;
    };
    queueUrl?: string;
    queueArn?: string;
    eventBridgeRuleArn?: string;
    triggerLambdaArn?: string;
    stateMachineArn?: string;
    roleArn?: string;
  };
}

export interface Pipeline extends PipelineResponse {}

export interface PipelineListResponse {
  status: string;
  message: string;
  data: {
    pipelines: PipelineResponse[];
  };
}

export interface PipelineSearchMetadata {
  totalResults: number;
  pageSize: number;
  nextToken?: string;
}
