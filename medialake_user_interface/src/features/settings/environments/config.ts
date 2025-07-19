// Environment configuration values
export const environmentConfig = {
  defaultEnvironment: "production",
  environmentTypes: ["development", "staging", "production"] as const,
} as const;

export type EnvironmentType =
  (typeof environmentConfig.environmentTypes)[number];

export const defaultColumnVisibility = {
  name: true,
  region: true,
  status: true,
  created_at: true,
  updated_at: false, // Hidden by default
};

export default environmentConfig;
