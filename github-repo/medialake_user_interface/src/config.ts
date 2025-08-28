import { environmentConfig } from "@/features/settings/environments/config";

// Core application configuration
export const config = {
  apiEndpoint: process.env.REACT_APP_API_ENDPOINT || "/api",
  environment: environmentConfig,
} as const;

export const { apiEndpoint } = config;

export default config;
