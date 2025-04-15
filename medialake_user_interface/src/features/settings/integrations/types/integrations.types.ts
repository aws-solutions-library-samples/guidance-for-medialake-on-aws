export interface IntegrationAuth {
    type: 'apiKey' | 'awsIam';
    credentials: {
        apiKey?: string;
        iamRole?: string;
    };
}

export interface IntegrationStatus {
    state: 'Active' | 'Disabled' | 'Error';
    lastSuccessfulConnection?: string;  // ISO timestamp
    lastError?: {
        message: string;
        timestamp: string;  // ISO timestamp
    };
}

export interface Integration {
    id: string;
    name: string;
    type: string;
    status: string;
    configuration: Record<string, any>;
    createdAt: string;
    updatedAt: string;
}

export interface IntegrationsResponse {
    status: string;
    message: string;
    data: Integration[];
}

export interface IntegrationsError {
    status?: number;
    message: string;
}

// DTOs for API requests
export interface CreateIntegrationDto {
    nodeId: string;
    integrationType: string;
    description: string;
    integrationEnabled: boolean;
    createdDate: string;
    modifiedDate: string;
    auth: IntegrationAuth;
}

export interface UpdateIntegrationDto {
    description?: string;
    auth?: IntegrationAuth;
    status?: Partial<IntegrationStatus>;
}

export interface IntegrationFormData {
    description: string;
    nodeId: string;
    auth: IntegrationAuth;
}

export interface IntegrationFilters {
    id: string;
    columnId: string;
    value: string;
}

export interface IntegrationSorting {
    id: string;
    columnId: string;
    desc: boolean;
}