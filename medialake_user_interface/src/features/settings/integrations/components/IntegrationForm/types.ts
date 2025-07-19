import { Environment } from "@/types/environment";

export interface IntegrationNode {
  nodeId: string;
  info: {
    title: string;
    description: string;
  };
  auth?: {
    authMethod?: "awsIam" | "apiKey";
  };
}

export interface IntegrationFormResult {
  id: string;
  nodeId: string;
  [key: string]: any;
}

export interface IntegrationFormProps {
  open: boolean;
  onClose: () => void;
  filteredNodes?: IntegrationNode[];
  onSubmitSuccess?: (result: IntegrationFormResult) => void;
  onSubmit?: (data: IntegrationFormData) => Promise<void>;
  editingIntegration?: {
    id: string;
    name: string;
    type: string;
    status: string;
    description: string;
    configuration: Record<string, any>;
    createdAt: string;
    updatedAt: string;
  } | null;
}

export interface IntegrationFormData {
  nodeId: string;
  description: string;
  auth: {
    type: "awsIam" | "apiKey";
    credentials: {
      apiKey?: string;
      iamRole?: string;
    };
  };
}

export interface IntegrationListItemProps {
  node: IntegrationNode;
  selected: boolean;
  onSelect: (node: IntegrationNode) => void;
}

export interface IntegrationConfigurationProps {
  formData: IntegrationFormData;
  onSubmit: (data: IntegrationFormData) => Promise<any>;
  onBack: () => void;
  onClose: () => void;
}

export interface StepperHeaderProps {
  activeStep: number;
  steps: string[];
}
