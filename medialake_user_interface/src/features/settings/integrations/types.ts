export interface IntegrationNode {
  nodeId: string;
  info: {
    title: string;
    description: string;
  };
  auth?: {
    authMethod: "awsIam" | "apiKey";
  };
}

export interface Integration {
  id: string;
  nodeId: string;
  description: string;
  environmentId: string;
  auth: {
    type: "awsIam" | "apiKey";
    credentials: {
      apiKey?: string;
      iamRole?: string;
    };
  };
  status: "active" | "inactive" | "error";
  createdAt: string;
  updatedAt: string;
}
