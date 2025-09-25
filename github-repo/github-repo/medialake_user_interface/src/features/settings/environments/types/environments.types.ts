import {
  Environment as BaseEnvironment,
  EnvironmentCreate as BaseEnvironmentCreate,
  EnvironmentUpdate as BaseEnvironmentUpdate,
} from "@/types/environment";

export type Environment = BaseEnvironment;
export type EnvironmentCreate = BaseEnvironmentCreate;
export type EnvironmentUpdate = BaseEnvironmentUpdate;

export interface EnvironmentsResponse {
  status: string;
  message: string;
  data: {
    environments: Environment[];
  };
}

export interface EnvironmentResponse {
  status: string;
  message: string;
  data: Environment;
}

export interface EnvironmentError {
  status?: number;
  message: string;
}
