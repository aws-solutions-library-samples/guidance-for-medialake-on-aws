// API endpoint configuration
export const apiEndpoint = process.env.REACT_APP_API_ENDPOINT || '/api';

// Other configuration values can be added here as needed
export const config = {
    apiEndpoint,
} as const;

export default config;
