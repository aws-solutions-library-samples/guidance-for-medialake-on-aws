export interface OutputType {
  name: string;
  description?: string;
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
  inputTypes?: string[];
  outputTypes?: string[] | OutputType[];
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
  label: string;
  type: "string" | "number" | "boolean" | "array";
  schema: any;
  description: string;
  required: boolean;
  defaultValue?: any;
}

export interface NodeMethod {
  name: string;
  description: string;
  parameters: NodeMethodParameter[];
}

export interface NodeConnection {
  entityType: string;
  connectionConfig: {
    type?: string[];
    types?: Array<{
      name: string;
      description?: string;
    }>;
  };
  methodId: string;
  connectionType: string;
  nodeId: string;
}

export interface NodeConnections {
  incoming: Record<string, NodeConnection[]>;
  outgoing: Record<string, NodeConnection[]>;
}

export interface Node {
  info: NodeInfo;
  auth: NodeAuth;
  nodeId?: string;
  methods: NodeMethod[];
  connections?: NodeConnections;
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
