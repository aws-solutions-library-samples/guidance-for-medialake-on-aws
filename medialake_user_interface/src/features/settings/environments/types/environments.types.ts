export interface Environment {
    environment_id: string;
    name: string;
    status: 'active' | 'disabled';
    region: string;
    tags: {
        'cost-center': string;
        team: string;
        [key: string]: string;
    };
    created_at: string;
    updated_at: string;
}

export interface EnvironmentCreate {
    name: string;
    region: string;
    status?: 'active' | 'disabled';
    tags: {
        'cost-center': string;
        team: string;
        [key: string]: string;
    };
}

export interface EnvironmentUpdate {
    name?: string;
    status?: 'active' | 'disabled';
    region?: string;
    tags?: {
        'cost-center': string;
        team: string;
        [key: string]: string;
    };
}

export interface EnvironmentsResponse {
    status: string;
    message: string;
    data?: {
        environments: Environment[];
    };
}

export interface EnvironmentResponse {
    status: string;
    message: string;
    data?: Environment;
}

export interface EnvironmentError {
    status: string;
    message: string;
}
