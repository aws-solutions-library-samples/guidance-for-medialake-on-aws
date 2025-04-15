import { Environment } from '@/types/environment';

export interface IntegrationNode {
    nodeId: string;
    info: {
        title: string;
        description: string;
    };
    auth?: {
        authMethod?: 'awsIam' | 'apiKey';
    };
}

export interface IntegrationFormProps {
    open: boolean;
    onClose: () => void;
    filteredNodes?: IntegrationNode[];
}

export interface IntegrationFormData {
    nodeId: string;
    description: string;
    auth: {
        type: 'awsIam' | 'apiKey';
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
    onSubmit: (data: IntegrationFormData) => Promise<void>;
    onBack: () => void;
    onClose: () => void;
}

export interface StepperHeaderProps {
    activeStep: number;
    steps: string[];
}
