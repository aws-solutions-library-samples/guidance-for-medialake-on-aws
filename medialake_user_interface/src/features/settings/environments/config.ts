// Environment configuration values
export const environmentConfig = {
    defaultEnvironment: 'production',
    environmentTypes: ['development', 'staging', 'production'] as const,
} as const;

export type EnvironmentType = typeof environmentConfig.environmentTypes[number];

export default environmentConfig;
